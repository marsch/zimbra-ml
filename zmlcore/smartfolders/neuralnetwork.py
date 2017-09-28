"""
created: 9/8/2017
(c) copyright 2017 Synacor, Inc

This is a neural network that can take both a small number of words from the subject and body, and
a few features of the e-mail, generated by relationships of the contacts and domains in the address block
to the user account as analytics, as well as any other features that may be useful.
"""
from neon.models import Model
from neon.layers import MergeMultistream, LSTM, Affine, RecurrentSum, Tree, BranchNode, SkipNode, Conv, Pooling
from neon.initializers import GlorotUniform, Kaiming
from neon.optimizers import Adam
from neon.transforms import Softmax, Logistic, Rectlin, Rectlinclip, Explin, Tanh


class ClassifierNetwork(Model):
    def __init__(self, overlapping_classes=None, exclusive_classes=None, analytics_input=True,
                 recurrent=True, width=100,
                 optimizer=Adam()):
        self.width = width
        self.overlapping_classes = overlapping_classes
        self.recurrent = recurrent

        # we must have some exclusive classes
        if exclusive_classes is None:
            self.exclusive_classes = ['finance', 'promos', 'social', 'forums', 'updates']
        else:
            self.exclusive_classes = exclusive_classes

        init = GlorotUniform()
        activation = Rectlin(slope=1E-05)
        gate = Tanh()

        input_layers = self.input_layers(analytics_input, init, activation, gate)

        if self.overlapping_classes is None:
            output_layers = [Affine(len(self.exclusive_classes), init, activation=Softmax())]
        else:
            output_branch = BranchNode(name='overlapping_exclusive')
            output_layers = Tree([[SkipNode(),
                                   output_branch,
                                   Affine(len(self.overlapping_classes), init, activation=Tanh())],
                                  [output_branch,
                                   Affine(len(self.exclusive_classes), init, activation=Softmax())]])
        layers = [input_layers,
                  # this is where inputs meet, and where we may want to add depth or
                  # additional functionality
                  Affine(20, init, activation=Explin()),
                  output_layers]
        super(ClassifierNetwork, self).__init__(layers, optimizer=optimizer)

    def _epoch_fit(self, dataset, callbacks):
        """
        Just insert ourselves to shuffle the dataset each epoch
        :param dataset:
        :param callbacks:
        :return:
        """
        if hasattr(dataset, 'shuffle'):
            dataset.shuffle()

        return super(ClassifierNetwork, self)._epoch_fit(dataset, callbacks)

    def input_layers(self, analytics_input, init, activation, gate):
        """
        return the input layers. we currently support convolutional and LSTM
        :return:
        """
        if self.recurrent:
            if analytics_input:
                # support analytics + content
                input_layers = MergeMultistream([
                    # [LSTM(300, init, init_inner=init, activation=activation, gate_activation=gate),
                    [LSTM(300, init, init_inner=init, activation=activation, gate_activation=gate),
                     RecurrentSum()],
                    [Affine(30, init, activation=activation)]],
                    'stack')
            else:
                # content only
                input_layers = [LSTM(600, init, init_inner=init, activation=activation, gate_activation=gate),
                                RecurrentSum()]
        else:
            if analytics_input:
                # support analytics + content
                input_layers = MergeMultistream([
                    [
                        Conv((1, 1, 2), padding=0, init=Kaiming(), activation=activation),
                        Conv((3, 1, 4), padding=0, init=Kaiming(), activation=activation),
                        Conv((5, 1, 6), padding=0, init=Kaiming(), activation=activation),
                        Conv((3, 1, 12), strides={'str_h': 2, 'str_w': 1}, padding=0, init=Kaiming(),
                             activation=activation),
                        Conv((5, 1, 18), padding=0, init=Kaiming(), activation=activation),
                        Conv((3, 3, 36), strides={'str_h': 2, 'str_w': 1}, padding=1, init=Kaiming(),
                             activation=activation),
                        Conv((3, 2, 54), padding=1, init=Kaiming(), activation=activation),
                        Conv((1, 3, 108), strides={'str_h': 1, 'str_w': 2}, padding=1, init=Kaiming(),
                             activation=Logistic()),
                    ],
                    [Affine(20, init, activation=Logistic())]],
                    'stack')
            else:
                # content only
                input_layers = [
                    Conv((1, 1, 2), padding=0, init=Kaiming(), activation=activation),
                    Conv((3, 1, 4), padding=0, init=Kaiming(), activation=activation),
                    Conv((5, 1, 6), padding=0, init=Kaiming(), activation=activation),
                    Conv((3, 1, 12), strides={'str_h': 2, 'str_w':1}, padding=0, init=Kaiming(), activation=activation),
                    Conv((5, 1, 18), padding=0, init=Kaiming(), activation=activation),
                    Conv((3, 3, 36), strides={'str_h': 2, 'str_w':1}, padding=1, init=Kaiming(), activation=activation),
                    Conv((3, 2, 54), padding=1, init=Kaiming(),
                         activation=activation),
                    Conv((1, 3, 108), strides={'str_h': 1, 'str_w': 2}, padding=1, init=Kaiming(),
                         activation=Logistic()),
                ]

        return input_layers