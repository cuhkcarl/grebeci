from mxnet import gluon
from mxnet import autograd
from mxnet import nd
from mxnet import image
from mxnet.gluon import nn
import mxnet as mx
import numpy as np
from time import time
import matplotlib.pyplot as plt

class TestDataLoader(object): 
    def __init__(self, dataset, batch_size): 
        self.dataset = dataset
        self.batch_size = batch_size

    def __iter__(self): 
        dataset = self.dataset[:]
        X = dataset[0]
        y = dataset[1]
        n = X.shape[0]
        last_i = 0
        for i in range(n//self.batch_size):
            last_i = i
            batch_x = X[i*self.batch_size: (i+1)*self.batch_size]
            batch_x = nd.transpose(batch_x, axes=(0, 3, 1, 2))
            yield (batch_x, y[i*self.batch_size: (i+1)*self.batch_size])
        batch_x = X[(last_i+1)*self.batch_size:]
        batch_x = nd.transpose(batch_x, axes=(0, 3, 1, 2))
        yield (batch_x, y[(last_i+1)*self.batch_size: ])


    def __len__(self): 
        return len(self.dataset[0])//self.batch_size


class DataLoader(object): 
    def __init__(self, dataset, batch_size, shuffle=True, resize=None): 
        self.dataset = dataset
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.resize = resize

    def __iter__(self): 
        dataset = self.dataset[:]
        X = dataset[0]
        y = nd.array(dataset[1])
        n = X.shape[0]
        resize = self.resize
        if self.shuffle: 
            idx = np.arange(n)
            np.random.shuffle(idx)
            X = nd.array(X.asnumpy()[idx])
            y = nd.array(y.asnumpy()[idx])
        for i in range(n//self.batch_size):
            batch_x = X[i*self.batch_size: (i+1)*self.batch_size]
            if resize:
                new_data = nd.zeros(shape=(batch_x.shape[0], resize, resize, batch_x.shape[3]))
                for j in range(batch_x.shape[0]):
                    new_data[j] = image.imresize(batch_x[j], resize, resize)
                batch_x = new_data
            batch_x = nd.transpose(batch_x, axes=(0, 3, 1, 2))
            yield (batch_x, y[i*self.batch_size: (i+1)*self.batch_size])

    def __len__(self): 
        return len(self.dataset[0])//self.batch_size
            

def load_data_fashion_mnist(batch_size, resize=None, root="~/.mxnet/datasets/fashion-mnist"):
    """download the fashion mnist dataest and then load into memory"""
    def transform_mnist(data, label):
        # transform a batch of examples
        if resize:
            n = data.shape[0]
            new_data = nd.zeros((n, resize, resize, data.shape[3]))
            for i in range(n):
                new_data[i] = image.imresize(data[i], resize, resize)
            data = new_data
        # change data from batch x height x weight x channel to batch x channel x height x weight
        return nd.transpose(data.astype('float32'), (0,3,1,2))/255, label.astype('float32')
    mnist_train = gluon.data.vision.FashionMNIST(root=root, train=True, transform=transform_mnist)
    mnist_test = gluon.data.vision.FashionMNIST(root=root, train=False, transform=transform_mnist)
    train_data = DataLoader(mnist_train, batch_size, shuffle=True)
    test_data = DataLoader(mnist_test, batch_size, shuffle=False)
    return (train_data, test_data)

def try_gpu():
    """If GPU is available, return mx.gpu(0); else return mx.cpu()"""
    try:
        ctx = mx.gpu()
        _ = nd.array([0], ctx=ctx)
    except:
        ctx = mx.cpu()
    return ctx

def try_all_gpus():
    """Return all available GPUs, or [mx.gpu()] if there is no GPU"""
    ctx_list = []
    try:
        for i in range(16):
            ctx = mx.gpu(i)
            _ = nd.array([0], ctx=ctx)
            ctx_list.append(ctx)
    except:
        pass
    if not ctx_list:
        ctx_list = [mx.cpu()]
    return ctx_list

def SGD(params, lr):
    for param in params:
        param[:] = param - lr * param.grad

def accuracy(output, label):
    return nd.mean(output.argmax(axis=1)==label).asscalar()

def _get_batch(batch, ctx):
    """return data and label on ctx"""
    if isinstance(batch, mx.io.DataBatch):
        data = batch.data[0]
        label = batch.label[0]
    else:
        data, label = batch
    return (gluon.utils.split_and_load(data, ctx),
            gluon.utils.split_and_load(label, ctx),
            data.shape[0])

def softmax(X):
    X_max = nd.max(X, axis=1, keepdims=True)
    X = X - X_max
    exp = nd.exp(X)
    partition = nd.sum(exp, axis=1, keepdims=True)
    return exp / partition

def cross_entropy(yhat, y):
    return - nd.log(nd.pick(yhat, y, axis=1, keepdims=True))


def evaluate_accuracy(data_iter, net, ctx=[mx.cpu()]):
    acc = .0
    total_loss = .0
    n = 0
    for data, label in data_iter:
        data = data.as_in_context(ctx)
        label = label.as_in_context(ctx)
        output = net(data)
        prob = softmax(output)
        loss = cross_entropy(prob, label)
        total_loss += nd.sum(loss).asscalar()
        n += loss.shape[0]
        acc += accuracy(output, label)
    return acc / len(data_iter), total_loss / n

def predict(data_iter, net, filename, ctx=[mx.cpu()]):
    
    outf = open(filename, 'w')
    for data, iden in data_iter:
        data = data.as_in_context(ctx)
        output = net(data)
        # print(output)
        prob = softmax(output)
        for i in range(len(iden)):
            # print(prob[i])
            outf.write('%s,%f\n' % (iden[i], prob[i][1].asscalar()))


# def evaluate_accuracy(data_iterator, net, ctx=[mx.cpu()]):
#     if isinstance(ctx, mx.Context):
#         ctx = [ctx]
#     acc = nd.array([0])
#     n = 0.
#     total_loss = .0
#     if isinstance(data_iterator, mx.io.MXDataIter):
#         data_iterator.reset()
#     for batch in data_iterator:
#         data, label, batch_size = _get_batch(batch, ctx)

#         output = net(data)
#         prob = softmax(output)
#         loss = cross_entropy(prob, label)
#         total_loss += nd.sum(loss).asscalar()

#         for X, y in zip(data, label):
#             acc += nd.sum(net(X).argmax(axis=1)==y).copyto(mx.cpu())
#             n += y.size
#             print(y.size)
#         acc.wait_to_read() # don't push too many operators into backend
#     return acc.asscalar() / n, total_loss / n

def train(train_data, test_data, net, loss, trainer, ctx, num_epochs, print_batches=None):
    """Train a network"""
    print("Start training on ", ctx)
    if isinstance(ctx, mx.Context):
        ctx = [ctx]
    for epoch in range(num_epochs):
        train_loss, train_acc, n, m = 0.0, 0.0, 0.0, 0.0
        if isinstance(train_data, mx.io.MXDataIter):
            train_data.reset()
        start = time()
        for i, batch in enumerate(train_data):
            data, label, batch_size = _get_batch(batch, ctx)
            losses = []
            with autograd.record():
                outputs = [net(X) for X in data]
                losses = [loss(yhat, y) for yhat, y in zip(outputs, label)]
            for l in losses:
                l.backward()
            train_acc += sum([(yhat.argmax(axis=1)==y).sum().asscalar()
                              for yhat, y in zip(outputs, label)])
            train_loss += sum([l.sum().asscalar() for l in losses])
            trainer.step(batch_size)
            n += batch_size
            m += sum([y.size for y in label])
            if print_batches and (i+1) % print_batches == 0:
                print("Batch %d. Loss: %f, Train acc %f" % (
                    n, train_loss/n, train_acc/m
                ))

        test_acc = evaluate_accuracy(test_data, net, ctx)
        print("Epoch %d. Loss: %.3f, Train acc %.2f, Test acc %.2f Time %.1f sec" % (
            epoch, train_loss/n, train_acc/m, test_acc, time() - start
        ))

class Residual(nn.HybridBlock):
    def __init__(self, channels, same_shape=True, **kwargs):
        super(Residual, self).__init__(**kwargs)
        self.same_shape = same_shape
        with self.name_scope():
            strides = 1 if same_shape else 2
            self.conv1 = nn.Conv2D(channels, kernel_size=3, padding=1,
                                  strides=strides)
            self.bn1 = nn.BatchNorm()
            self.conv2 = nn.Conv2D(channels, kernel_size=3, padding=1)
            self.bn2 = nn.BatchNorm()
            if not same_shape:
                self.conv3 = nn.Conv2D(channels, kernel_size=1,
                                      strides=strides)

    def hybrid_forward(self, F, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        if not self.same_shape:
            x = self.conv3(x)
        return F.relu(out + x)

def resnet18(num_classes):
    net = nn.HybridSequential()
    with net.name_scope():
        net.add(
            nn.BatchNorm(),
            nn.Conv2D(64, kernel_size=3, strides=1),
            nn.MaxPool2D(pool_size=3, strides=2),
            Residual(64),
            Residual(64),
            Residual(128, same_shape=False),
            Residual(128),
            Residual(256, same_shape=False),
            Residual(256),
            nn.GlobalAvgPool2D(),
            nn.Dense(num_classes)
        )
    return net

def show_images(imgs, nrows, ncols, figsize=None):
    """plot a list of images"""
    if not figsize:
        figsize = (ncols, nrows)
    _, figs = plt.subplots(nrows, ncols, figsize=figsize)
    for i in range(nrows):
        for j in range(ncols):
            figs[i][j].imshow(imgs[i*ncols+j].asnumpy())
            figs[i][j].axes.get_xaxis().set_visible(False)
            figs[i][j].axes.get_yaxis().set_visible(False)
    plt.show()
