'''
This code is to construct the complete SAR model by combining backbone+encoder+decoder as one integrated model.
'''
import torch
import torch.nn as nn
from .backbone import backbone
# from .shufflenetv2 import shufflenet_v2_x1_0
from .mobilenetv2 import MobileNetV2
from .encoder import encoder
from .decoder import decoder

__all__ = ['sar']

class sar(nn.Module):
    def __init__(self, channel, feature_height, feature_width, embedding_dim, output_classes, hidden_units=512, layers=2, keep_prob=1.0, seq_len=40, device='cpu'):
        super(sar, self).__init__()
        '''
        channel: channel of input image
        feature_height: feature height of backbone feature map
        embedding_dim: embedding dimension for a word
        output_classes: number of output classes for the one hot encoding of a word
        hidden_units: hidden units for both LSTM encoder and decoder
        layers: layers for both LSTM encoder and decoder, should be set to 2
        keep_prob: keep_prob probability dropout for LSTM encoder
        seq_len: decoding sequence length
        '''
        # self.backbone = backbone(channel)
        # self.backbone = shufflenet_v2_x1_0()
        self.backbone = MobileNetV2()
        self.encoder_model = encoder(feature_height, 512, hidden_units, layers, keep_prob, device)
        self.decoder_model = decoder(output_classes, feature_height, feature_width, 512, hidden_units, seq_len, device)
        self.embedding_dim = embedding_dim
        self.output_classes = output_classes
        self.hidden_units = hidden_units
        self.layers = layers
        self.keep_prob = keep_prob
        self.seq_len = seq_len
        self.device = device

    def forward(self,x,y):
        '''
        x: input images [batch, channel, height, width]
        y: output labels [batch, seq_len, output_classes]
        '''
        V = self.backbone(x) # (batch, feature_depth, feature_height, feature_width)
        hw = self.encoder_model(V) # (batch, hidden_units)
        outputs, attention_weights = self.decoder_model(hw, y, V) # [batch, seq_len, output_classes], [batch, seq_len, 1, feature_height, feature_width]

        return outputs, attention_weights, V, hw

# unit test
if __name__ == '__main__':
    '''
    Need to change the import to do unit test:
    from backbone import backbone
    from encoder import encoder
    from decoder import decoder
    '''
    torch.manual_seed(0)

    batch_size = 2
    Height = 12
    Width = 24
    Channel = 3
    output_classes = 94
    embedding_dim = 512
    hidden_units = 512
    layers = 2
    keep_prob = 1.0
    seq_len = 40

    feature_height = Height // 4
    feature_width = Width // 8

    y = torch.randn(batch_size, seq_len, output_classes)
    x = torch.randn(batch_size, Channel, Height, Width)
    print("Input image size is:", x.shape)
    print("Input label size is:", y.shape)

    model = sar(Channel, feature_height, feature_width, embedding_dim, output_classes, hidden_units, layers, keep_prob, seq_len)

    predict1, att_weights1, V1, hw1 = model.train()(x,y)
    print("Prediction size is:", predict1.shape)
    print("Attention weight size is:", att_weights1.shape)

    predict2, att_weights2, V2, hw2 = model.train()(x,y)
    print("Prediction size is:", predict2.shape)
    print("Attention weight size is:", att_weights2.shape)

    print("Difference:", torch.sum(predict1-predict2))