"""
created: 9/21/2017
(c) copyright 2017 Synacor, Inc

This is a simple iterator for training data that iterates over both the inputs and targets for training
neural networks. It expects the inputs and targets to be independent iterables of the same number of elements
and simply provides the interface Intel's Nervana Neon Model likes to see
"""
import numpy as np
from neon.data import NervanaDataIterator

class TrainingIterator(NervanaDataIterator):
    def __init__(self, inputs, targets=None, name=None):
        """
        Just an easy way to feed data to a neon model
        :param name:
        """
        assert len(inputs) == len(targets) or targets is None
        super(TrainingIterator, self).__init__(name=name)
        self.inputs = inputs
        self.targets = targets

    @property
    def nbatches(self):
        return len(self.inputs)

    @property
    def ndata(self):
        return self.nbatches

    def reset(self):
        pass

    def __iter__(self):
        """
        Returns a new minibatch of data with each call.

        Yields:
            tuple: The next minibatch which includes both features and labels.
        """
        for x, y in zip(self.inputs, self.targets if not self.targets is None else self.inputs):
            yield (x, y)

    def shuffle(self):
        a = np.arange(len(self.inputs))
        np.random.shuffle(a)
        self.inputs = [self.inputs[i] for i in a]
        if not self.targets is None:
            self.targets = [self.targets[i] for i in a]


class BatchIterator(NervanaDataIterator):
    def __init__(self, inputs, targets=None, steps=None, name=None):
        """
        This takes two lists with samples separated in the 0 dimension. If for recurrent input, the number
        of recurrent items is also in the 0 dimension. Convolutional input should also be prepared with the following
        axes:
        0 - num_samples
        1 - channels
        2 - width
        3 - height
        :param inputs: MUST be a list of numpy arrays of inputs separated by each sequence element and batches on axis 0
        :param targets: MUST be a list of numpy arrays of targets separated by each element and batch on axis 0
        :param steps: list of the number of recurrent steps in each stream of the input (element of input list)
        :param name:
        """
        super(BatchIterator, self).__init__(name=name)

        if steps is None:
            steps = [1 for _ in inputs]
        elif not isinstance(steps, list):
            steps = [steps]

        if not isinstance(inputs, list):
            inputs = [inputs]

        if not targets is None and not isinstance(targets, list):
            targets = [targets]

        # may be recurrent
        self.ndata = int(len(inputs[0]) // steps[0])
        self.steps = steps
        self.start = [0 for _ in inputs]

        # transpose inputs, putting axis 0 at the end
        self.inputs = [self.be.array(x.transpose([i for i in range(1, len(x.shape))] + [0])) for x in inputs]
        self.targets = None if targets is None else [self.be.array(y.transpose(
            [i for i in range(1, len(y.shape))] + [0]
        )) for y in targets]

    def reset(self):
        self.start = [0 for _ in self.start]

    @property
    def nbatches(self):
        return int(-((self.start[0] / self.steps[0]) - self.ndata) // self.be.bsz)

    def __iter__(self):
        """
        Returns a new minibatch of data with each call.

        Yields:
            tuple: The next minibatch which includes both features and labels.
        """
        pos = self.start[0] // self.steps[0]
        while pos + self.be.bsz <= self.ndata:
            y = None if self.targets is None else [a[:,pos:pos + self.be.bsz] for a in self.targets]

            x = []
            for a, i in zip(self.inputs, range(len(self.inputs))):
                inc = self.steps[i] * self.be.bsz
                if len(a.shape) == 2:
                    x += [a[:,self.start[i]:self.start[i] + inc].reshape(
                        tuple([n for n in a.shape[:len(a.shape)-1]] + [self.be.bsz]))]
                elif len(a.shape) == 3:
                    x += [a[:, :, self.start[i]:self.start[i] + inc].reshape(
                        tuple([n for n in a.shape[:len(a.shape)-1]] + [self.be.bsz]))]
                elif len(a.shape) == 4:
                    x += [a[:, :, :, self.start[i]:self.start[i] + inc].reshape(
                        tuple([n for n in a.shape[:len(a.shape)-1]] + [self.be.bsz]))]
                elif len(a.shape) == 5:
                    x += [a[:, :, :, :, self.start[i]:self.start[i] + inc].reshape(
                        tuple([n for n in a.shape[:len(a.shape)-1]] + [self.be.bsz]))]
                else:
                    assert False
                self.start[i] += inc

            yield x if len(x) > 1 else x[0], y if y is None or len(y) > 1 else y[0]
            pos = self.start[0] // self.steps[0]

        self.reset()

    def shuffle(self):
        a = np.arange(self.ndata)
        np.random.shuffle(a)
        for x, i in zip(self.inputs, range(len(self.inputs))):
            shuffles = np.array([[v * self.steps[i] + j for j in range(self.steps[i])] for v in a]).flatten()
            x[:] = self.be.take(x, shuffles, axis=len(x.shape)-1)
        if not self.targets is None:
            for x in self.targets:
                x[:] = self.be.take(x, a, axis=len(x.shape)-1)

    def test_shuffle(self):
        """
        this stores markers at the beginning (and end if recurrent) of each section of each input and target
        it then shuffles and verifies that all markers still match
        :return:
        """
        a = np.arange(self.ndata)
        for i in a:
            for x, s in zip(self.inputs, self.steps):
                if len(x.shape) == 2:
                    x[:, i * s:(i * s) + s] = float(i)
                elif len(x.shape) == 3:
                    x[:, :, i * s:(i * s) + s] = float(i)
                elif len(x.shape) == 4:
                    x[:, :, :, i * s:(i * s) + s] = float(i)
                else:
                    assert False
            for x in self.targets:
                x[:,i] = float(i)
        self.shuffle()
        for i in a:
            for x, s in zip(self.inputs, self.steps):
                if len(x.shape) == 2:
                    z_if_ok = sum([0 if (self.targets[0][:, i].get()[0, 0] ==
                                         y.get()[0, 0] for y in [x[:, i * s:(i * s) + s]])
                                  else 1])
                elif len(x.shape) == 3:
                    z_if_ok = sum([0 if (self.targets[0][:, i].get()[0, 0] ==
                                         y.get()[0, 0] for y in [x[:, :, i * s:(i * s) + s]])
                                  else 1])
                elif len(x.shape) == 4:
                    z_if_ok = sum([0 if (self.targets[0][:, i].get()[0, 0] ==
                                         y.get()[0, 0] for y in [x[:, :, :, i * s:(i * s) + s]])
                                  else 1])
                elif len(x.shape) == 5:
                    z_if_ok = sum([0 if (self.targets[0][:, i].get()[0, 0] ==
                                         y.get()[0, 0] for y in [x[:, :, :, :, i * s:(i * s) + s]])
                                   else 1])
                else:
                    assert False
                assert z_if_ok == 0
