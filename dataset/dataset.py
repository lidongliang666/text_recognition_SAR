'''
This code is to build various dataset for SAR
'''
import string
import cv2
import torch.utils.data as data
import os
import torch
import numpy as np
import xml.etree.ElementTree as ET
from scipy.io import loadmat
import pdb

def dictionary_generator(END='END', PADDING='PAD', UNKNOWN='UNK'):
    '''
    END: end of sentence token
    PADDING: padding token
    UNKNOWN: unknown character token
    '''
    voc = list(string.printable[:-6]) # characters including 9 digits + 26 lower cases + 26 upper cases + 33 punctuations
    
    # update the voc with 3 specifical chars
    voc.append(END)
    voc.append(PADDING)
    voc.append(UNKNOWN)

    char2id = dict(zip(voc, range(len(voc))))
    id2char = dict(zip(range(len(voc)), voc))

    return voc, char2id, id2char

def end_cut(indices, char2id, id2char):
    '''
    indices: numpy array or list of character indices
    charid: char to id conversion
    id2char: id to char conversion
    '''
    cut_indices = []
    for id in indices:
        if id != char2id['END']:
            if id != char2id['UNK'] and id != char2id['PAD']:
                cut_indices.append(id2char[id])
        else:
            break
    return ''.join(cut_indices)

def svt_xml_extractor(label_path):
    '''
    This code is to extract xml labels from SVT dataset
    Input:
    label_path: xml label path file
    Output:
    dict_img: [image_name, bounding box, labels, lexicon]
    '''
    # create element tree object
    tree = ET.parse(label_path)

    # get root element
    root = tree.getroot()

    # create empty list for news items
    dict_img = []

    # iterate news items
    for item in root.findall('image'):
        name = item.find('imageName').text.split('/')[-1]
        lexicon = item.find('lex').text.split(',')
        rec = item.find('taggedRectangles')
        for r in rec.findall('taggedRectangle'):
            x = int(r.get('x'))
            y = int(r.get('y'))
            w = int(r.get('width'))
            h = int(r.get('height'))
            bdb = (x,y,w,h)
            labels = r.find('tag').text
            dict_img.append([name, bdb,labels,lexicon])

    return dict_img

def iiit5k_mat_extractor(label_path):
    '''
    This code is to extract mat labels from IIIT5k dataset
    Input:
    label_path: mat label path file
    Output:
    dict_img: [image_name, labels, small_lexicon, medium_lexicon]
    '''
    # create empty list for news items
    dict_img = []

    mat_contents = loadmat(label_path)

    if 'traindata' in mat_contents:
        key = 'traindata'
    else:
        key = 'testdata'
    for i in range(len(mat_contents[key][0])):
        name = mat_contents[key][0][i][0][0]
        label = mat_contents[key][0][i][1][0]
        #small_lexi = [item[0] for item in mat_contents[key][0][i][2][0]]
        #medium_lexi = [item[0] for item in mat_contents[key][0][i][3][0]]
        dict_img.append([name, label])

    return dict_img

def synthtext_mat_extractor(label_path):
    '''
    This code is to extract mat labels from SynthText dataset
    Input:
    label_path: mat label path file
    Output:
    dict_img: [image_name, bounding box, labels]
    '''
    # create empty list for news items
    dict_img = []

    mat_contents = loadmat(label_path)

    for i in range(len(mat_contents['imnames'][0])):
        image_name = mat_contents['imnames'][0][i][0].split('/')[-1]
        word_bdbs = []
        if len(mat_contents['wordBB'][0][i].shape) == 3:
            for bdb_idx in range(mat_contents['wordBB'][0][i].shape[-1]):
                word_bdb = mat_contents['wordBB'][0][i][:,:,bdb_idx] # shape (2,4), i.e., 4 points for (x,y)
                xmin = min(word_bdb[0,:])
                ymin = min(word_bdb[1,:])
                xmax = max(word_bdb[0,:])
                ymax = max(word_bdb[1,:])
                word_bdbs.append((int(xmin),int(ymin),int(xmax),int(ymax)))
        else:
            word_bdb = mat_contents['wordBB'][0][i][:,:] # shape (2,4), i.e., 4 points for (x,y)
            xmin = min(word_bdb[0,:])
            ymin = min(word_bdb[1,:])
            xmax = max(word_bdb[0,:])
            ymax = max(word_bdb[1,:])
            word_bdbs.append((int(xmin),int(ymin),int(xmax),int(ymax)))

        if len(mat_contents['charBB'][0][i].shape) == 3:
            for bdb_idx in range(mat_contents['charBB'][0][i].shape[-1]):
                char_bdb = mat_contents['charBB'][0][i][:,:,bdb_idx] # shape (2,4), i.e., 4 points for (x,y)
        else:
            char_bdb = mat_contents['charBB'][0][i][:,:] # shape (2,4), i.e., 4 points for (x,y)

        labels = []
        for label_idx in range(mat_contents['txt'][0][i].shape[0]):
            label_total = mat_contents['txt'][0][i][label_idx]
            L = label_total.split('\n')
            for l in L:
                l = l.strip()
                l = list(l.split(' '))
                l = [item for item in l if item != '']
                labels += l
        if len(word_bdbs) != len(labels):
            print("Wrong parsing for labels in SynthText dataset!")
            exit(1)
        for word_bdb, label in zip(word_bdbs, labels):
            dict_img.append([image_name, word_bdb, label])

    return dict_img

class svt_dataset_builder(data.Dataset):
    def __init__(self, height, width, seq_len, total_img_path, xml_path):
        '''
        height: input height to model
        width: input width to model
        total_img_path: path with all images
        xml_path: xml labeling file
        seq_len: sequence length
        '''
        # parse xml file and create fully ready dataset
        self.total_img_path = total_img_path
        self.height = height
        self.width = width
        self.seq_len = seq_len
        self.dictionary = svt_xml_extractor(xml_path)
        self.total_img_name = os.listdir(total_img_path)
        self.dataset = []
        self.voc, self.char2id, _ = dictionary_generator()
        self.output_classes = len(self.voc)
        for items in self.dictionary:
            if items[0] in self.total_img_name:
                self.dataset.append([items[0],items[1],items[2]])

    def __getitem__(self, index):
        img_name, bdb, label = self.dataset[index]
        IMG = cv2.imread(os.path.join(self.total_img_path,img_name))
        x, y, w, h = bdb
        (H, W, _) = IMG.shape
        x = max(0, x)
        x = min(W-1, x)
        y = max(0, y)
        y = min(H-1, y)
        w = max(0, w)
        w = min(W, w)
        h = max(0, h)
        h = min(H-1, h)
        # image processing:
        IMG = IMG[y:y+h,x:x+w,:] # crop
        IMG = cv2.resize(IMG, (self.width, self.height)) # resize
        IMG = (IMG - 127.5)/127.5 # normalization to [-1,1]
        IMG = torch.FloatTensor(IMG) # convert to tensor [H, W, C]
        IMG = IMG.permute(2,0,1) # [C, H, W]
        y_true = np.ones(self.seq_len)*self.char2id['PAD'] # initialize y_true with 'PAD', size [seq_len]
        # label processing
        for i, c in enumerate(label):
            index = self.char2id[c]
            y_true[i] = index
        y_true[-1] = self.char2id['END'] # always put 'END' in the end
        y_true = y_true.astype(int) # must to integer index for one-hot encoding
        # convert to one-hot encoding
        y_onehot = np.eye(self.output_classes)[y_true] # [seq_len, output_classes]

        return IMG, torch.FloatTensor(y_onehot)

    def __len__(self):
        return len(self.dataset)

class iiit5k_dataset_builder(data.Dataset):
    def __init__(self, height, width, seq_len, total_img_path, annotation_path):
        '''
        height: input height to model
        width: input width to model
        total_img_path: path with all images
        annotation_path: mat labeling file
        seq_len: sequence length
        '''
        self.total_img_path = total_img_path
        self.height = height
        self.width = width
        self.seq_len = seq_len
        self.dictionary = iiit5k_mat_extractor(annotation_path)
        self.total_img_name = os.listdir(total_img_path)
        self.dataset = []
        self.voc, self.char2id, _ = dictionary_generator()
        self.output_classes = len(self.voc)

        for items in self.dictionary:
            if items[0].split('/')[-1] in self.total_img_name:
                self.dataset.append([items[0].split('/')[-1],items[1]])

    def __getitem__(self, index):
        img_name, label = self.dataset[index]
        IMG = cv2.imread(os.path.join(self.total_img_path,img_name))
        IMG = cv2.resize(IMG, (self.width, self.height)) # resize
        IMG = (IMG - 127.5)/127.5 # normalization to [-1,1]
        IMG = torch.FloatTensor(IMG) # convert to tensor [H, W, C]
        IMG = IMG.permute(2,0,1) # [C, H, W]
        y_true = np.ones(self.seq_len)*self.char2id['PAD'] # initialize y_true with 'PAD', size [seq_len]
        # label processing
        for i, c in enumerate(label):
            index = self.char2id[c]
            y_true[i] = index
        y_true[-1] = self.char2id['END'] # always put 'END' in the end
        y_true = y_true.astype(int) # must to integer index for one-hot encoding
        # convert to one-hot encoding
        y_onehot = np.eye(self.output_classes)[y_true] # [seq_len, output_classes]

        return IMG, torch.FloatTensor(y_onehot)

    def __len__(self):
        return len(self.dataset)

class iiit5k_dataset_builder2(data.Dataset):
    def __init__(self, height, width, seq_len, total_img_path, annotation_path,min_w=48,max_w=160):
        '''
        height: input height to model
        width: input width to model
        total_img_path: path with all images
        annotation_path: mat labeling file
        seq_len: sequence length
        '''
        self.total_img_path = total_img_path
        self.height = height
        self.width = width
        self.min_w = min_w
        self.max_w = max_w
        self.seq_len = seq_len
        self.dictionary = iiit5k_mat_extractor(annotation_path)
        self.total_img_name = os.listdir(total_img_path)
        self.dataset = []
        self.voc, self.char2id, _ = dictionary_generator()
        self.output_classes = len(self.voc)

        for items in self.dictionary:
            if items[0].split('/')[-1] in self.total_img_name:
                self.dataset.append([items[0].split('/')[-1],items[1]])

    def __getitem__(self, index):
        img_name, label = self.dataset[index]
        background = np.random.randint(0,255,(self.height,self.width,3))
        IMG = cv2.imread(os.path.join(self.total_img_path,img_name))
        o_h,o_w,_ = IMG.shape
        r_w = int(o_w * self.height / o_h)
        IMG = cv2.resize(IMG,(r_w,self.height))

        if r_w<self.min_w:
            IMG = cv2.resize(IMG,(self.min_w,self.height))
            background[:,:self.min_w] = IMG
        elif r_w>self.max_w:
            IMG = cv2.resize(IMG,(self.max_w,self.height))
            background[:,:self.max_w] = IMG
        else :
            background[:,:r_w] = IMG
        # #保存 可视化
        # cv2.imwrite('random.jpg',background)
        # raise ''

        # IMG = cv2.resize(IMG, (self.width, self.height)) # resize
        background = (background - 127.5)/127.5 # normalization to [-1,1]
        background = torch.FloatTensor(background) # convert to tensor [H, W, C]
        background = background.permute(2,0,1) # [C, H, W]
        y_true = np.ones(self.seq_len)*self.char2id['PAD'] # initialize y_true with 'PAD', size [seq_len]
        # label processing
        for i, c in enumerate(label):
            index = self.char2id[c]
            y_true[i] = index
        y_true[-1] = self.char2id['END'] # always put 'END' in the end
        y_true = y_true.astype(int) # must to integer index for one-hot encoding
        # convert to one-hot encoding
        y_onehot = np.eye(self.output_classes)[y_true] # [seq_len, output_classes]

        return background, torch.FloatTensor(y_onehot)

    def __len__(self):
        return len(self.dataset)

class syn90k_dataset_builder(data.Dataset):
    def __init__(self, height, width, seq_len, total_img_path):
        '''
        height: input height to model
        width: input width to model
        total_img_path: path with all images
        seq_len: sequence length
        '''
        self.total_img_path = total_img_path
        self.height = height
        self.width = width
        self.seq_len = seq_len
        self.total_img_name = os.listdir(total_img_path)
        self.dataset = []
        self.voc, self.char2id, _ = dictionary_generator()
        self.output_classes = len(self.voc)

        for img_name in self.total_img_name:
            _, label, _ = img_name.split('_')
            self.dataset.append([img_name, label])

    def __getitem__(self, index):
        img_name, label = self.dataset[index]
        IMG = cv2.imread(os.path.join(self.total_img_path,img_name))
        IMG = cv2.resize(IMG, (self.width, self.height)) # resize
        IMG = (IMG - 127.5)/127.5 # normalization to [-1,1]
        IMG = torch.FloatTensor(IMG) # convert to tensor [H, W, C]
        IMG = IMG.permute(2,0,1) # [C, H, W]
        y_true = np.ones(self.seq_len)*self.char2id['PAD'] # initialize y_true with 'PAD', size [seq_len]
        # label processing
        for i, c in enumerate(label):
            index = self.char2id[c]
            y_true[i] = index
        y_true[-1] = self.char2id['END'] # always put 'END' in the end
        y_true = y_true.astype(int) # must to integer index for one-hot encoding
        # convert to one-hot encoding
        y_onehot = np.eye(self.output_classes)[y_true] # [seq_len, output_classes]

        return IMG, torch.FloatTensor(y_onehot)

    def __len__(self):
        return len(self.dataset)

class talenglish_dataset_builder(data.Dataset):
    def __init__(self, height, width, seq_len, total_img_path):
        '''
        height: input height to model
        width: input width to model
        total_img_path: path with all images
        seq_len: sequence length
        '''
        self.total_img_path = total_img_path
        self.height = height
        self.width = width
        self.seq_len = seq_len
        self.total_img_name = os.listdir(total_img_path)
        self.dataset = []
        self.voc, self.char2id, _ = dictionary_generator()
        self.output_classes = len(self.voc)

        for img_name in self.total_img_name:
            _, label, _ = img_name.split('_')
            self.dataset.append([img_name, label])



class synthtext_dataset_builder(data.Dataset):
    def __init__(self, height, width, seq_len, total_img_path, annotation_path):
        '''
        height: input height to model
        width: input width to model
        total_img_path: path with all images
        annotation_path: mat labeling file
        seq_len: sequence length
        '''
        self.total_img_path = total_img_path
        self.height = height
        self.width = width
        self.seq_len = seq_len
        self.dictionary = synthtext_mat_extractor(annotation_path)
        self.total_img_name = os.listdir(total_img_path)
        self.dataset = []
        self.voc, self.char2id, _ = dictionary_generator()
        self.output_classes = len(self.voc)

        for items in self.dictionary:
            if items[0] in self.total_img_name:
                self.dataset.append([items[0],items[1],items[2]])

    def __getitem__(self, index):
        img_name, bdb, label = self.dataset[index]
        IMG = cv2.imread(os.path.join(self.total_img_path,img_name))
        xmin, ymin, xmax, ymax = bdb
        (H, W, _) = IMG.shape
        xmin = max(0, xmin)
        xmin = min(W-1, xmin)
        ymin = max(0, ymin)
        ymin = min(H-1, ymin)
        xmax = max(0, xmax)
        xmax = min(W-1, xmax)
        ymax = max(0, ymax)
        ymax = min(H-1, ymax)
        # image processing:
        IMG = IMG[ymin:ymax+1,xmin:xmax+1,:] # crop
        IMG = cv2.resize(IMG, (self.width, self.height)) # resize
        IMG = (IMG - 127.5)/127.5 # normalization to [-1,1]
        IMG = torch.FloatTensor(IMG) # convert to tensor [H, W, C]
        IMG = IMG.permute(2,0,1) # [C, H, W]
        y_true = np.ones(self.seq_len)*self.char2id['PAD'] # initialize y_true with 'PAD', size [seq_len]
        # label processing
        for i, c in enumerate(label):
            index = self.char2id[c]
            y_true[i] = index
        y_true[-1] = self.char2id['END'] # always put 'END' in the end
        y_true = y_true.astype(int) # must to integer index for one-hot encoding
        # convert to one-hot encoding
        y_onehot = np.eye(self.output_classes)[y_true] # [seq_len, output_classes]

        return IMG, torch.FloatTensor(y_onehot)

    def __len__(self):
        return len(self.dataset)

class test_dataset_builder(data.Dataset):
    def __init__(self, height, width, img_path):
        '''
        height: input height to model
        width: input width to model
        img_path: path with images
        '''
        self.height = height
        self.width = width
        self.img_path = img_path
        self.dataset = [image_name for image_name in os.listdir(self.img_path)]

    def __getitem__(self, index):
        IMG = cv2.imread(os.path.join(self.img_path, self.dataset[index]))
        # image processing:
        IMG = cv2.resize(IMG, (self.width, self.height)) # resize
        IMG = (IMG - 127.5)/127.5 # normalization to [-1,1]
        IMG = torch.FloatTensor(IMG) # convert to tensor [H, W, C]
        IMG = IMG.permute(2,0,1) # [C, H, W]

        return IMG, self.dataset[index]

    def __len__(self):
        return len(self.dataset)

# unit test
if __name__ == '__main__':

    # img_path = '../svt/img/'
    # train_xml_path = '../svt/train.xml'
    # test_xml_path = '../svt/test.xml'

    img_path_iiit = '../IIIT5K/train/'
    annotation_path_iiit = '../IIIT5K/traindata.mat'

    # img_path_syn90k = '../Syn90k/train/'

    # img_path_synthtext = '../SynthText/train/'
    # annotation_path_synthtext = '../SynthText/gt.mat'

    height = 48 # input height pixel
    width = 160 # input width pixel
    seq_len = 40 # sequence length

    voc, char2id, id2char = dictionary_generator()

    # train_dict = svt_xml_extractor(train_xml_path)
    # print("Dictionary for training set is:", train_dict)

    # train_dataset = svt_dataset_builder(height, width, seq_len, img_path, train_xml_path)

    # for i, item in enumerate(train_dataset):
        # print(item[0].shape,item[1].shape)

    # test_dataset = svt_dataset_builder(height, width, seq_len, img_path, test_xml_path)

    # train_dict_iiit = iiit5k_mat_extractor(annotation_path_iiit)
    # print("Dictionary for training set is:", train_dict_iiit)

    # train_dataset_iiit5k = iiit5k_dataset_builder(height, width, seq_len, img_path_iiit, annotation_path_iiit)
    train_dataset_iiit5k2 = iiit5k_dataset_builder2(height, width, seq_len, img_path_iiit, annotation_path_iiit)

    # train_dataset_syn90k = syn90k_dataset_builder(height, width, seq_len, img_path_syn90k)

    # train_dict_synthtext = synthtext_mat_extractor(annotation_path_synthtext)
    #print("Dictionary for training set is:", train_dict_synthtext)

    # train_dataset_synthtext = synthtext_dataset_builder(height, width, seq_len, img_path_synthtext, annotation_path_synthtext)

    # for i, item in enumerate(train_dataset):
    #     print(item[0].shape,item[1].shape)
    #     IMG = item[0].permute(1,2,0)
    #     IMG = IMG.detach().numpy()
    #     IMG = (IMG*127.5+127.5).astype(np.uint8)
    #     cv2.imwrite('../test/svt_'+str(i)+'.jpg', IMG)

    # for i, item in enumerate(train_dataset_iiit5k):
    #     print(item[0].shape,item[1].shape)
    #     IMG = item[0].permute(1,2,0)
    #     IMG = IMG.detach().numpy()
    #     IMG = (IMG*127.5+127.5).astype(np.uint8)
    #     cv2.imwrite('../test/iiit_'+str(i)+'.jpg', IMG)

    for i, item in enumerate(train_dataset_iiit5k2):
        print(item[0].shape,item[1].shape)
        IMG = item[0].permute(1,2,0)
        IMG = IMG.detach().numpy()
        IMG = (IMG*127.5+127.5).astype(np.uint8)
        cv2.imwrite('../test/iiit_'+str(i)+'.jpg', IMG)

    # for i, item in enumerate(train_dataset_syn90k):
    #     print(item[0].shape,item[1].shape)
    #     IMG = item[0].permute(1,2,0)
    #     IMG = IMG.detach().numpy()
    #     IMG = (IMG*127.5+127.5).astype(np.uint8)
    #     cv2.imwrite('../test/syn90k_'+str(i)+'.jpg', IMG)

    # for i, item in enumerate(train_dataset_synthtext):
    #     print(item[0].shape,item[1].shape)
    #     IMG = item[0].permute(1,2,0)
    #     IMG = IMG.detach().numpy()
    #     IMG = (IMG*127.5+127.5).astype(np.uint8)
    #     target = item[1].max(1)[1] # [seq_len]
    #     label = end_cut(target.detach().cpu().numpy(), char2id, id2char)
    #     print(label)
    #     cv2.imwrite('../test/synthtext_'+str(i)+'.jpg', IMG)