import multiprocessing as mtp
import sys

sys.path.append('autograder')
sys.path.append('./')

import traceback
from enum import Enum

import numpy as np
import torch
import torch.nn as nn
from torch.autograd import Variable

from helpers import *
from mytorch.nn.activations import *
from mytorch.nn.batchnorm import BatchNorm1d
from mytorch.nn.dropout import Dropout
from mytorch.nn.linear import Linear
from mytorch.nn.loss import *
from mytorch.nn.sequential import Sequential
from mytorch.optim.adam import Adam
from mytorch.tensor import Tensor


# Dropout tests
def test_dropout_forward():
    np.random.seed(11785)
    
    # run on small model forward only
    x = Tensor.randn(5, 10)
    model = Sequential(Linear(10, 5), ReLU(), Dropout(p=0.6))
    my_output = model(x)

    test_output = load_numpy_array('autograder/hw1_bonus_autograder/outputs/dropout_forward.npy')
    return assertions_all(my_output.data, test_output, "test_dropout_forward", 1e-5, 1e-6)

def test_dropout_forward_backward():
    np.random.seed(11785)
    
    # run on small model, forward backward (no step)
    model = Sequential(Linear(10, 20), ReLU(), Dropout(p=0.6))
    x, y = generate_dataset_for_mytorch_model(model, 5)
    x, y = Tensor(x), Tensor(y)
    criterion = CrossEntropyLoss()
    out = model(x)
    
    test_out = load_numpy_array('autograder/hw1_bonus_autograder/outputs/backward_output.npy')
    
    if not assertions_all(out.data, test_out, "test_dropout_forward_backward_output", 1e-5, 1e-6):
        return False
    
    loss = criterion(out, y)
    loss.backward()
    
    assert model[0].weight.grad is not None, "Linear layer must have gradient."
    assert model[0].weight.grad.grad is None, "Final gradient tensor must not have its own gradient"
    assert model[0].weight.grad.grad_fn is None, "Final gradient tensor must not have its own grad function"
    assert model[0].weight.requires_grad, "Weight tensor must have requires_grad==True"
    assert model[0].weight.is_parameter, "Weight tensor must be marked as a parameter tensor"

    test_grad = load_numpy_array('autograder/hw1_bonus_autograder/outputs/backward_grad.npy')
    
    return assertions_all(model[0].weight.grad.data, test_grad, "test_dropout_forward_backward_grad", 1e-5, 1e-6)

def test_big_model_step():
    np.random.seed(11785)
    
    # run a big model
    model = Sequential(Linear(10, 15), ReLU(), Dropout(p=0.2), 
                       Linear(15, 20), ReLU(), Dropout(p=0.1))
    x, y = generate_dataset_for_mytorch_model(model, 4)
    x, y = Tensor(x), Tensor(y)
    criterion = CrossEntropyLoss()
    optimizer = Adam(model.parameters(), lr=1e-3, betas=(0.9, 0.999), eps=1e-08)
    
    # check output correct
    out = model(x)
    test_out = load_numpy_array('autograder/hw1_bonus_autograder/outputs/big_output.npy')

    if not assertions_all(out.data, test_out, "test_big_model_step_out", 1e-5, 1e-6):
        return False
    
    # run backward
    loss = criterion(out, y)
    loss.backward()
    
    # check params are correct (sorry this is ugly)
    assert model[0].weight.grad is not None, "Linear layer must have gradient."
    assert model[0].weight.grad.grad is None, "Final gradient tensor must not have its own gradient"
    assert model[0].weight.grad.grad_fn is None, "Final gradient tensor must not have its own grad function"
    assert model[0].weight.requires_grad, "Weight tensor must have requires_grad==True"
    assert model[0].weight.is_parameter, "Weight tensor must be marked as a parameter tensor"
    assert model[3].weight.grad is not None, "Linear layer must have gradient."
    assert model[3].weight.grad.grad is None, "Final gradient tensor must not have its own gradient"
    assert model[3].weight.grad.grad_fn is None, "Final gradient tensor must not have its own grad function"
    assert model[3].weight.requires_grad, "Weight tensor must have requires_grad==True"
    assert model[3].weight.is_parameter, "Weight tensor must be marked as a parameter tensor"
    
    # check gradient for linear layer at idx 0 is correct
    test_grad = load_numpy_array('autograder/hw1_bonus_autograder/outputs/big_grad.npy')
    if not assertions_all(model[0].weight.grad.data, test_grad, "test_big_model_grad_0", 1e-5, 1e-6):
        return False
    
    # check gradient for linear layer at idx 3 is correct
    test_grad = load_numpy_array('autograder/hw1_bonus_autograder/outputs/big_grad_3.npy')
    if not assertions_all(model[3].weight.grad.data, test_grad, "test_big_model_grad_3", 1e-5, 1e-6):
        return False

    # weight update with adam
    optimizer.step()
    
    # check updated weight values
    assert model[0].weight.requires_grad, "Weight tensor must have requires_grad==True"
    assert model[0].weight.is_parameter, "Weight tensor must be marked as a parameter tensor"

    test_weights_3 = load_numpy_array('autograder/hw1_bonus_autograder/outputs/big_weight_update_3.npy')
    test_weights_0 = load_numpy_array('autograder/hw1_bonus_autograder/outputs/big_weight_update_0.npy')
    
    return assertions_all(model[0].weight.data, test_weights_0, "test_big_weight_update_0", 1e-5, 1e-6) and \
        assertions_all(model[3].weight.data, test_weights_3, "test_big_weight_update_3", 1e-5, 1e-6)

##############################
# Utilities for testing MLPs #
##############################

def test_forward(mytorch_model, mytorch_criterion=None, batch_size=(2,5)):
    """
    Tests forward, printing whether a mismatch occurs in forward or backwards.

    Returns whether the test succeeded.
    """
    pytorch_model = get_same_pytorch_mlp(mytorch_model)
    batch_size = np.random.randint(*batch_size) if type(batch_size) == tuple\
        else batch_size
    x, y = generate_dataset_for_mytorch_model(mytorch_model, batch_size)
    pytorch_criterion = get_same_pytorch_criterion(mytorch_criterion)

    forward_passed, _ = forward_(mytorch_model, mytorch_criterion,
                                 pytorch_model, pytorch_criterion, x, y)
    if not forward_passed:
        print("Forward failed")
        return False

    return True


def test_forward_backward(mytorch_model, mytorch_criterion=None,
                          batch_size=(2,5)):
    """
    Tests forward and back, printing whether a mismatch occurs in forward or
    backwards.

    Returns whether the test succeeded.
    """
    pytorch_model = get_same_pytorch_mlp(mytorch_model)
    batch_size = np.random.randint(*batch_size) if type(batch_size) == tuple\
        else batch_size
    x, y = generate_dataset_for_mytorch_model(mytorch_model, batch_size)
    pytorch_criterion = get_same_pytorch_criterion(mytorch_criterion)

    forward_passed, (mx, my, px, py) = \
        forward_(mytorch_model, mytorch_criterion,
                 pytorch_model, pytorch_criterion, x, y)
    if not forward_passed:
        print("Forward failed")
        return False

    backward_passed = backward_(mx, my, mytorch_model, px, py, pytorch_model)
    if not backward_passed:
        print("Backward failed")
        return False

    return True


def test_step(mytorch_model, mytorch_optimizer, train_steps, eval_steps,
              mytorch_criterion=None, batch_size=(2, 5)):
    """
    Tests subsequent forward, back, and update operations, printing whether
    a mismatch occurs in forward or backwards.

    Returns whether the test succeeded.
    """
    pytorch_model = get_same_pytorch_mlp(mytorch_model)
    pytorch_optimizer = get_same_pytorch_optimizer(
        mytorch_optimizer, pytorch_model)
    pytorch_criterion = get_same_pytorch_criterion(mytorch_criterion)
    batch_size = np.random.randint(*batch_size) if type(batch_size) == tuple\
        else batch_size
    x, y = generate_dataset_for_mytorch_model(mytorch_model, batch_size)

    mytorch_model.train()
    pytorch_model.train()
    for s in range(train_steps):
        pytorch_optimizer.zero_grad()
        mytorch_optimizer.zero_grad()

        forward_passed, (mx, my, px, py) = \
            forward_(mytorch_model, mytorch_criterion,
                     pytorch_model, pytorch_criterion, x, y)
        if not forward_passed:
            print("Forward failed")
            return False

        backward_passed = backward_(
            mx, my, mytorch_model, px, py, pytorch_model)
        if not backward_passed:
            print("Backward failed")
            return False

        pytorch_optimizer.step()
        mytorch_optimizer.step()

    mytorch_model.eval()
    pytorch_model.eval()
    for s in range(eval_steps):
        pytorch_optimizer.zero_grad()
        mytorch_optimizer.zero_grad()

        forward_passed, (mx, my, px, py) = \
            forward_(mytorch_model, mytorch_criterion,
                     pytorch_model, pytorch_criterion, x, y)
        if not forward_passed:
            print("Forward failed")
            return False
    
    # Check that each weight tensor is still configured correctly 
    try:
        for param in mytorch_model.parameters():
            assert param.requires_grad, "Weights should have requires_grad==True!"
            assert param.is_leaf, "Weights should have is_leaf==True!"
            assert param.is_parameter, "Weights should have is_parameter==True!"
    except Exception as e:
        traceback.print_exc()
        return False

    return True


def get_same_pytorch_mlp(mytorch_model):
    """
    Returns a pytorch Sequential model matching the given mytorch mlp, with
    weights copied over.
    """
    layers = []
    for l in mytorch_model.layers:
        if isinstance(l, Linear):
            layers.append(nn.Linear(l.in_features, l.out_features))
            layers[-1].weight = nn.Parameter(
                torch.tensor(l.weight.data).double())
            layers[-1].bias = nn.Parameter(torch.tensor(l.bias.data).double())
        elif isinstance(l, BatchNorm1d):
            layers.append(nn.BatchNorm1d(int(l.num_features)))
            layers[-1].weight = nn.Parameter(
                torch.tensor(l.gamma.data).double())
            layers[-1].bias = nn.Parameter(torch.tensor(l.beta.data).double())
        elif isinstance(l, ReLU):
            layers.append(nn.ReLU())
        elif isinstance(l, Dropout):
            layers.append(nn.Dropout())
        else:
            raise Exception("Unrecognized layer in mytorch model")
    pytorch_model = nn.Sequential(*layers)
    return pytorch_model.double()


def get_same_pytorch_optimizer(mytorch_optimizer, pytorch_mlp):
    """
    Returns a pytorch optimizer matching the given mytorch optimizer, except
    with the pytorch mlp parameters, instead of the parametesr of the mytorch
    mlp
    """
    lr = mytorch_optimizer.lr
    betas = mytorch_optimizer.betas
    eps = mytorch_optimizer.eps
    return torch.optim.Adam(pytorch_mlp.parameters(), lr=lr, betas=betas, eps=eps)


def get_same_pytorch_criterion(mytorch_criterion):
    """
    Returns a pytorch criterion matching the given mytorch optimizer
    """
    if mytorch_criterion is None:
        return None
    return nn.CrossEntropyLoss()


def generate_dataset_for_mytorch_model(mytorch_model, batch_size):
    """
    Generates a fake dataset to test on.

    Returns x: ndarray (batch_size, in_features),
            y: ndarray (batch_size,)
    where in_features is the input dim of the mytorch_model, and out_features
    is the output dim.
    """
    in_features = get_mytorch_model_input_features(mytorch_model)
    out_features = get_mytorch_model_output_features(mytorch_model)
    x = np.random.randn(batch_size, in_features)
    y = np.random.randint(out_features, size=(batch_size,))
    return x, y


def forward_(mytorch_model, mytorch_criterion, pytorch_model,
             pytorch_criterion, x, y):
    """
    Calls forward on both mytorch and pytorch models.

    x: ndrray (batch_size, in_features)
    y: ndrray (batch_size,)

    Returns (passed, (mytorch x, mytorch y, pytorch x, pytorch y)),
    where passed is whether the test passed

    """
    # forward
    pytorch_x = Variable(torch.tensor(x).double(), requires_grad=True)
    pytorch_y = pytorch_model(pytorch_x)
    if not pytorch_criterion is None:
        pytorch_y = pytorch_criterion(pytorch_y, torch.LongTensor(y))
    mytorch_x = Tensor(x, requires_grad=True)
    mytorch_y = mytorch_model(mytorch_x)
    if not mytorch_criterion is None:
        mytorch_y = mytorch_criterion(mytorch_y, Tensor(y))

    # forward check
    if not assertions_all(mytorch_y.data, pytorch_y.detach().numpy(), 'y'):
        return False, (mytorch_x, mytorch_y, pytorch_x, pytorch_y)

    return True, (mytorch_x, mytorch_y, pytorch_x, pytorch_y)


def backward_(mytorch_x, mytorch_y, mytorch_model, pytorch_x, pytorch_y, pytorch_model):
    """
    Calls backward on both mytorch and pytorch outputs, and returns whether
    computed gradients match.
    """
    mytorch_y.backward()
    pytorch_y.sum().backward()
    return check_gradients(mytorch_x, pytorch_x, mytorch_model, pytorch_model)


def check_gradients(mytorch_x, pytorch_x, mytorch_model, pytorch_model):
    """
    Checks computed gradients, assuming forward has already occured.

    Checked gradients are the gradients of linear weights and biases, and the
    gradient of the input.
    """

    if not assertions_all(mytorch_x.grad.data, pytorch_x.grad.detach().numpy(), 'dx'):
        return False
    mytorch_linear_layers = get_mytorch_linear_layers(mytorch_model)
    pytorch_linear_layers = get_pytorch_linear_layers(pytorch_model)
    for mytorch_linear, pytorch_linear in zip(mytorch_linear_layers, pytorch_linear_layers):
        pytorch_dW = pytorch_linear.weight.grad.detach().numpy()
        pytorch_db = pytorch_linear.bias.grad.detach().numpy()
        mytorch_dW = mytorch_linear.weight.grad.data
        mytorch_db = mytorch_linear.bias.grad.data

        if not assertions_all(mytorch_dW, pytorch_dW, 'dW'):
            return False
        if not assertions_all(mytorch_db, pytorch_db, 'db'):
            return False
    return True


def get_mytorch_model_input_features(mytorch_model):
    """
    Returns in_features for the first linear layer of a mytorch
    Sequential model.
    """
    return get_mytorch_linear_layers(mytorch_model)[0].in_features


def get_mytorch_model_output_features(mytorch_model):
    """
    Returns out_features for the last linear layer of a mytorch
    Sequential model.
    """
    return get_mytorch_linear_layers(mytorch_model)[-1].out_features


def get_mytorch_linear_layers(mytorch_model):
    """
    Returns a list of linear layers for a mytorch model.
    """
    return list(filter(lambda x: isinstance(x, Linear), mytorch_model.layers))


def get_pytorch_linear_layers(pytorch_model):
    """
    Returns a list of linear layers for a pytorch model.
    """
    return list(filter(lambda x: isinstance(x, nn.Linear), pytorch_model))
