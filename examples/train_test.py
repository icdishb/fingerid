"""
==============================================================================
Pipeline when train and test are sperated.
If only interested in cross validation on train set, use the pipeline of 
shen_ISMB2014.py.
==============================================================================
"""

import sys
import numpy
import warnings; warnings.filterwarnings('ignore')
# Comment the following line if fingerid has been installed,
# otherwise, leave it there
sys.path.append("../../fingerid")

from fingerid.preprocess.msparser import MSParser
from fingerid.preprocess.fgtreeparser import FragTreeParser
from fingerid.kernel.twodgaussiankernel import TwoDGaussianKernel
from fingerid.kernel.fgtreekernel import FragTreeKernel
from fingerid.kernel.mskernel import Kernel
from fingerid.kernel.mkl import mkl
from fingerid.model.trainSVM import trainModels
from fingerid.model.predSVM import predModels
from fingerid.kernel.twodgaussiankernel import TwoDGaussianKernel
from fingerid.preprocess.util import writeIDs
from fingerid.preprocess.util import centerTestKernel


if __name__ == "__main__":
    """Another pipeline when you have train/test instead of cross validation""" 
    # parse data
    print "parse data\n"
    fgtreeparser = FragTreeParser()
    msparser = MSParser()

    train_ms = msparser.parse_dir("test_data/train_ms/")
    test_ms = msparser.parse_dir("test_data/test_ms/")
    train_trees = fgtreeparser.parse_dir("test_data/train_trees")
    test_trees = fgtreeparser.parse_dir("test_data/test_trees")
    labels = numpy.loadtxt("test_data/train_output.txt")
    n_train, n_fp = labels.shape
    n_test = len(test_trees)

    # output the files corresponding to the spectra and fragmentation trees  
    writeIDs("spectras.txt",train_ms)
    writeIDs("fgtrees.txt", train_trees)

    # compute train and test kernels
    types = ["PPK","NB","NI","LB","LC","LI","RLB","RLI","CPC","CP2",
             "CPK","CSC"]
    train_km_list = []
    test_km_list = []

    # Can use mulitp process to speed up computation
    # as in shen_ISMB2014.py. But here only compute sequentially

    for ty in types:
        print "computing %s kernels" % ty
        if ty == "PPK":
            sm = 0.00001
            si = 100000
            # shoud select sm and si by cross validation
            kernel = TwoDGaussianKernel(sm, si)
            train_km = kernel.compute_train_kernel(train_ms)
            test_km = kernel.compute_test_kernel(test_ms, train_ms)
            train_km_list.append(train_km)
            test_km_list.append(centerTestKernel(test_km,train_km))
        else:
            kernel = FragTreeKernel()
            train_km = kernel.compute_train_kernel(train_trees, ty)
            if ty == "CPK": # to use CPK kernel, sm, and si are needed
                sm = 0.00001
                si = 100000
                train_km = kernel.compute_train_kernel(train_trees, ty, 
                                                       sm=sm, si=si)
                test_km = kernel.compute_test_kernel(test_trees, train_trees, 
                                                     ty, sm=sm, si=si)
            else:
                train_km = kernel.compute_train_kernel(train_trees, ty)
                test_km = kernel.compute_test_kernel(test_trees, train_trees,
                                                     ty)
            train_km_list.append(train_km)
            test_km_list.append(centerTestKernel(test_km,train_km))
    print 
    print "combine kernels\n"
    # compute combined train and test kernel
    train_ckm, w = mkl(train_km_list, labels, 'ALIGN')
    test_ckm = numpy.zeros((n_test, n_train))
    for i in range(len(types)):
        test_ckm = test_ckm + w[i]*test_km_list[i]
    # normalize combined test kernel matrix
    test_ckm = test_ckm / numpy.sum(w)

    # train with 4 processe
    print "train models and make prediction"
    # MODELS is the folder to store trained models.
    prob= True # Set prob=True if want probability output
    trainModels(train_ckm, labels, "MODELS", select_c=True, n_p=4, 
                prob=prob)

    #print models
    preds = predModels(test_ckm, n_fp, "MODELS", prob=prob)
    if prob:
        fmt = "%.4f"
    else:
        fmt = "%d"
    numpy.savetxt("predictions.txt", preds, fmt=fmt)








