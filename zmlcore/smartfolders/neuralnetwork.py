"""
created: 9/8/2017
(c) copyright 2017 Synacor, Inc

This is a neural network that can take both a small number of words from the subject and body, and
a few features of the e-mail, generated by relationships of the contacts and domains in the address block
to the user account as analytics, as well as any other features that may be useful.
"""
from neon.models.model import Model
from neon.layers import MergeMultistream, LSTM, Affine, RecurrentSum, Tree, BranchNode, SkipNode, Conv, Dropout
from neon.initializers import GlorotUniform, Kaiming
from neon.optimizers import Adam
from neon.transforms import Softmax, Logistic, Rectlin

class ClassifierNetwork(Model):
    def __init__(self, overlapping_classes=None, exclusive_classes=None, analytics_input=True,
                 network_type='conv_net', num_words=60, width=100, optimizer=Adam()):
        self.width = width
        self.num_words = num_words
        self.overlapping_classes = overlapping_classes
        self.analytics_input = analytics_input
        self.recurrent = network_type == 'lstm'

        # we must have some exclusive classes
        if exclusive_classes is None:
            self.exclusive_classes = ['finance', 'promos', 'social', 'forums', 'updates']
        else:
            self.exclusive_classes = exclusive_classes

        init = GlorotUniform()
        activation = Rectlin(slope=1E-05)
        gate = Logistic()

        input_layers = self.input_layers(analytics_input, init, activation, gate)

        if self.overlapping_classes is None:
            output_layers = [Affine(len(self.exclusive_classes), init, activation=Softmax())]
        else:
            output_branch = BranchNode(name='exclusive_overlapping')
            output_layers = Tree([[SkipNode(),
                                   output_branch,
                                   Affine(len(self.exclusive_classes), init, activation=Softmax())],
                                  [output_branch,
                                   Affine(len(self.overlapping_classes), init, activation=Logistic())]])
        layers = [input_layers,
                  # this is where inputs meet, and where we may want to add depth or
                  # additional functionality
                  # Dropout(keep=0.8),
                  # Affine(80 if self.num_words > 30 else 175, init, activation=activation),
                  Dropout(keep=0.8),
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
                    [LSTM(300, init, init_inner=Kaiming(), activation=activation, gate_activation=gate,
                          reset_cells=True),
                     RecurrentSum()],
                    [Affine(30, init, activation=activation)]],
                    'stack')
            else:
                # content only
                input_layers = [LSTM(300, init, init_inner=Kaiming(), activation=activation, gate_activation=gate,
                                     reset_cells=True),
                                RecurrentSum()]
        else:
            if analytics_input:
                # support analytics + content
                input_layers = MergeMultistream([self.conv_net(activation),
                                                 [Affine(30, init, activation=Logistic())]],
                                                'stack')
            else:
                # content only
                input_layers = self.conv_net(activation)

        return input_layers

    def conv_net(self, activation, init=Kaiming(), version=-1):
        if version == -1:
            return [
                Conv((2, self.width, self.width), padding={'pad_h': 1, 'pad_w': 0},
                     init=init, activation=activation),
                Dropout(keep=0.6),
                Conv((3, 1, 80), padding={'pad_h': 1, 'pad_w': 0}, init=init, activation=activation),
                Dropout(keep=0.925),
                Conv((4, 1, 100), padding={'pad_h': 1, 'pad_w': 0}, init=init, activation=activation),
                Dropout(keep=0.9),
                Conv((5, 1, 100), strides={'str_h': 2 if self.num_words > 59 else 1,
                                           'str_w': 1}, padding=0, init=init,
                     activation=activation),
                Dropout(keep=0.9),
                Conv((3, 1, 100), strides={'str_h': 2, 'str_w': 1}, padding=0, init=init,
                     activation=activation),
                Dropout(keep=0.9),
                Conv((7, 1, 80), strides={'str_h': 2, 'str_w': 1}, padding=0, init=init,
                     activation=activation)
            ]
