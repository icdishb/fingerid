"""
======================================================
Corss validation on the data using multiple processes.
======================================================

"""

from svmutil import *
import commands
import numpy
import random
import multiprocessing
import sys

class result():
    # internal class passed to by sub process
    def __init__(self, i, n):
        self.fp_ind = i # fingerprint index 
        self.pred_fp_ = numpy.zeros(n) # predicted fingerprints
        self.acc = 0 # cross validation accuracy
    
def internalCV_mp(kernel, labels, n_folds, pred_f, select_c=False, n_p=8):
    """
    Internel cross validation using train data.

    Parameters:
    -----------
    kernel, numpy 2d array, n_train*n_train, training kernel

    labels, numpy 2d array, n_train*n_fingerprints, training labels

    n_folds, number of cross validations

    pred_f, string, file to store predicted fingerprints in the CV

    select_c, bool, whether doing C selection in CV

    n_p, int, number of processes to use

    Note:

    Wrtie the cross validation predition fingerprints in pred_f
    """
    
    (n_x, n_x) = kernel.shape
    (n_x, n_y) = labels.shape
    x = kernel
    if n_y < n_p:
        n_p = n_y

    #cv_accs = numpy.zeros(n_y)
    pred_fp = numpy.zeros((n_x, n_y))

    tags = _label_folds(n_x, n_folds)
    result_queue = multiprocessing.Queue(n_y)

    task_dict = {}
    for i in range(n_y):
        task_dict[i%n_p] = []
    for i in range(n_y):
        task_dict[i%n_p].append(i)

    for i in range(n_p):
        if select_c:
            p = multiprocessing.Process(target=_CV_BestC, 
                  args=(result_queue, x, labels, task_dict[i], tags, n_folds,))
            p.start()
        else:
            p = multiprocessing.Process(target=_CV, 
                  args=(result_queue, x, labels, task_dict[i], tags, n_folds,))
            p.start()

    for i in range(n_y):
        res = result_queue.get()
        fp_ind = res.fp_ind
        pred_fp[:,fp_ind] = res.pred_fp_
        #cv_accs[fp_ind] = res.acc

    #w = open(cv_acc_f,"w")
    #w.write(" ".join(map(str,cv_accs)))
    #w.close()
    numpy.savetxt(pred_f, pred_fp, fmt="%d")

def _CV(Queue, x, labels, inds, tags, n_folds):
    """
    Internel cross validation using c = 1
    """
    for ind in inds:
        #print "cv on %d'th fingerprint" % ind
        n = len(x)
        pred = numpy.zeros(n)
        y = labels[:,ind]
        res = result(ind,n)
        for i in range(1,n_folds+1):
            test = tags == i
            train = ~(tags == i)
            test = numpy.array(range(n))[test].tolist()
            train = numpy.array(range(n))[train].tolist()

            train_km = x[numpy.ix_(train,train)]
            test_km = x[numpy.ix_(test,train)]

            train_label = y[train]
            test_label = y[test]
            n_train = len(train_km)
            n_test = len(test_km)

            train_km = numpy.append(numpy.array(range(1,n_train+1)).reshape(n_train,1), train_km,1).tolist()
            test_km = numpy.append(numpy.array(range(1,n_test+1)).reshape(n_test,1), test_km,1).tolist()
            prob = svm_problem(train_label, train_km, isKernel=True)
            param = svm_parameter('-t 4 -c 1 -b 0 -q')
            m = svm_train(prob,param)
            p_label, p_acc, p_val=svm_predict(test_label,test_km, m,'-b 0 -q')
            pred[numpy.ix_(test)] = p_label

        acc = sum(pred == y) / float(n)
        res.ind = ind
        res.pred_fp_ = pred
        res.acc = acc    
        Queue.put(res)


def _CV_BestC(Queue, x, labels, inds, tags, n_folds):
    """
    Internel cross validation using best C
    """
    for ind in inds:
        #print "cv on %d'th fingerprint" % ind
        n = len(x)
        y = labels[:,ind]
        C = numpy.array([2**-3,2**-2,2**-1,2**0,2**1,2**2,2**3,
         2**4,2**5,2**6,2**7])
        n_c = len(C)
        pred = numpy.zeros((n_c,n))

        res = result(ind,n)
        for i in range(1,n_folds+1):
            test = tags == i
            train = ~(tags == i)
            test = numpy.array(range(n))[test].tolist()
            train = numpy.array(range(n))[train].tolist()

            train_km = x[numpy.ix_(train,train)]
            test_km = x[numpy.ix_(test,train)]

            train_label = y[train]
            test_label = y[test]

            n_train = len(train_km)
            n_test = len(test_km)

            train_km = numpy.append(numpy.array(range(1,n_train+1)).reshape(n_train,1), train_km,1).tolist()
            test_km = numpy.append(numpy.array(range(1,n_test+1)).reshape(n_test,1), test_km,1).tolist()

            for j in range(n_c):
                c = C[j]
                prob = svm_problem(train_label, train_km, isKernel=True)
                param = svm_parameter('-t 4 -c %s -q' % c)
                m = svm_train(prob,param)
                p_label, p_acc, p_val=svm_predict(test_label,test_km, m,'-q')
                pred[j,numpy.ix_(test)] = p_label

        accs = numpy.sum(pred == numpy.array(y),1) / float(n)
        max_inds = numpy.where(max(accs)==accs)
        iind = max_inds[0][0]

        res.ind = ind
        res.pred_fp_ = pred[iind,]
        res.acc = accs[iind]    
        Queue.put(res)

def _label_folds(n_x ,n):
    """
    labeling the data by folds. Sequential lableing.
    """
    tag = [0]*n_x
    for i in range(n_x):
        tag[i] = i%n + 1
    return numpy.array(tag)

#def _label_by_mol(spectra,n_cv):
#    """
#    Lableing the data by molecules. Dividing the folds by kegg_id
#    """
#    mol_dict = {}
#    count = 1
#    for s in spectra:
#        if s.kegg_id not in mol_dict:
#            mol_dict[s.kegg_id] = count
#            count = count +1

#    n_mol = len(mol_dict)

#    a = range(1,n_mol+1)
#    random.seed(1986)
#    random.shuffle(a)
#    count = 0
#    for cid,num in mol_dict.items():
#        mol_dict[cid] = a[count]
#        count = count +1

#    mol_ids = []
#    for s in spectra:
#        mol_ids.append(mol_dict[s.kegg_id])

#    tags = []
#    n_seg = n_mol/n_cv+1
#    for mol_num in mol_ids:
#        tags.append(mol_num/n_seg+1)
#    return numpy.array(tags)

