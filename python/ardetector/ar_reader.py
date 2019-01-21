# ar_reader.py
# Andreas Brink-Kjaer
# Spring 2018
#
# Based on scripts by Caspar Aleksander Bang Jespersen
#
'''
This script contains function to read .txt files generated by preprocessing scripts in Matlab.
'''


import numpy as np
import tensorflow as tf
import os
import random
import ar_config
import collections
import ar_weights

Dataset = collections.namedtuple('Dataset', ['data', 'target', 'weights'])
Datasets = collections.namedtuple('Datasets',['train','val','test'])

class ArousalData:
    def __init__(self, pathname, config, num_steps=None, overwrite = 1, output_dir = '', test_split = 4):
        '''This function initializes the ArousalData class that is used to read data in batches from txt files.

        Args: 
            pathname: pathname to data files.
            config: config object from ar_config containing data directories.
            num_steps: number of iterations for training / testing.
            test_split: number of batches for testing. Should be set as high as possible without encountering memory issues.
        '''

        self.pathname = pathname
        self.filename = []
        self.features = []
        self.logits = []
        self.weights = []
        self.num_batches = 0
        self.batch_shift = 0
        self.overwrite = overwrite
        self.output_dir = output_dir
        self.num_steps = num_steps
        self.seq_in_file = []
        self.iter_batch = -1
        self.iter_steps = -1
        self.iter_rewind = -1
        self.test_split = test_split
        self.wake_def = config.wake_def
        self.config = config
        self.batch_size = config.batch_size
        self.batch_order = np.arange(1)
        self.validation_files = []
        self.is_training = config.is_training
        files = os.listdir(self.pathname)
        # Remove predicted files from list
        if self.overwrite == 0:
            self.output_files = os.listdir(self.output_dir)
            files = [x for x in files if x not in self.output_files]
        if self.is_training:
            file = random.choice(files)
        else:
            file = files[self.iter_rewind + 1]


        self.filename = os.path.join(self.pathname,file)
        self.validation_files.insert(0,self.filename)

        self.load()

    def __iter__(self):
        '''Iteration function'''
        return self

    def __next__(self):
        '''This function is used to iterate the class to get next batches.'''

        # Increment counters

        # Determine stopping criteria
        if self.num_steps is None:
            if (self.iter_batch + 1) > len(self.batch_order) or (self.iter_rewind + 1 > 50):
                raise StopIteration()
        else:
            if (self.iter_steps + 1) == self.num_steps:
                raise StopIteration()
            if self.iter_rewind > len(os.listdir(self.pathname))-2 and not self.is_training:
                raise StopIteration()
            if (self.iter_batch + 1) == len(self.batch_order):
                load_not_ok = True
                self.num_batches = 0

                while load_not_ok:
                    files = os.listdir(self.pathname)
                    if self.overwrite == 0:
                        files = [x for x in files if x not in self.output_files]
                    if self.is_training:
                        file = random.choice(files)
                    else:
                        if self.batch_shift == 0:
                            file = files[self.iter_rewind]
                            self.iter_rewind -= 1
                            self.batch_shift = 1
                        else:
                            file = files[self.iter_rewind + 1]
                            self.batch_shift = 0
                    print('New file. . .')
                    self.filename = os.path.join(self.pathname,file)
                    self.validation_files.insert(0,self.filename)
                    try:
                        self.load()       
                    except:
                        print('Error loading')

                    if self.num_batches>0:
                        load_not_ok = False

                    
        self.iter_batch += 1
        self.iter_steps += 1

        # Return relevant batch

        x, y, w = self.get_batch(self.iter_batch)
        return x, y, w

    def rewind(self):
        '''This function shuffles batches during training and in correct order for testing.'''

        # Reset iter
        self.iter_rewind += 1
        self.iter_batch = -1
        # Regular if not training
        if not self.is_training:
            self.batch_order = np.arange(self.num_batches)
            return
        else:
            # Randomize order
            self.batch_order = np.random.permutation(self.num_batches)
        print('(rewind data, shuffle)')

    def get_batch(self, batch_num):
        '''This function chooses and selects the next batch of data.

        Args:
            batch_num: next batch number.
        '''

        # Find indices
        batch_num_ordered = self.batch_order[batch_num]
        ind = np.arange(batch_num_ordered*self.batch_size, (batch_num_ordered+1)*self.batch_size,
                    step=1,
                    dtype=np.int)
        # Find batches
        x = self.features[ind, :, :]
        t = self.logits[ind,:]
        w = self.weights[ind,:]
        return x, t, w

    def load(self):
        '''Loads the next data file with load_txt and standerdizes and reshapes input data.'''

        # Load data
        data_set = self.load_txt()
        # Features
        self.features = data_set.data
        # Standerdization of data to (mean, std) = (0, 1)
        # Printout
        print(self.filename)
        print('mean: ',np.mean(self.features[:,:128]),np.mean(self.features[:,128:256]), np.mean(self.features[:,256:384]), np.mean(self.features[:,384:]))
        print('std: ',np.std(self.features[:,:128]),np.std(self.features[:,128:256]), np.std(self.features[:,256:384]), np.std(self.features[:,384:]))
        self.features[:,:128] = (self.features[:,:128] - np.mean(self.features[:,:128]))/np.std(self.features[:,:128])
        self.features[:,128:256] = (self.features[:,128:256] - np.mean(self.features[:,128:256]))/np.std(self.features[:,128:256])
        self.features[:,256:384] = (self.features[:,256:384] - np.mean(self.features[:,256:384]))/np.std(self.features[:,256:384])
        self.features[:,384:] = (self.features[:,384:] - np.mean(self.features[:,384:]))/np.std(self.features[:,384:])
        # Labels to logits
        self.logits = np.concatenate((np.eye(2)[data_set.target[:,0].astype('int')], np.eye(2)[data_set.target[:,1].astype('int')]),axis=1)
        self.weights = data_set.weights
        # Reshape data (batches, features, 1)
        self.features = np.expand_dims(self.features,2)
        self.num_batches = self.logits.shape[0] // self.batch_size
        assert np.round(self.num_batches, 0) == self.num_batches
        # Rewind
        self.rewind()

    def load_txt(self):
        '''Loads the next data file specified in self.filename.'''

        f = np.loadtxt(fname = self.filename,delimiter = ',')
        excess = f.shape[0] % self.batch_size
        if excess > 0:
            f = f[:-excess]
        if self.batch_shift == 1:
            f = f[int(self.batch_size/2):-int(self.batch_size/2)]
        data = f[:,:-2]
        target = f[:,-2:]
        # Select definition of wake = {W} or wake = {W,N1}
        target[target[:,-1] == 2] = self.wake_def
        self.seq_in_file = data.shape[0]
        # Get weights
        if self.is_training:
            approach = 1
        else:
            approach = 1
        w_ar = ar_weights.train_ar_weights(target[:,0],approach)
        w_w = ar_weights.train_ar_weights(target[:,1],1)
        w = np.transpose(np.vstack((w_ar,w_w)))

        return Dataset(data=data, target=target, weights=w)
