import tensorflow as tf
import numpy as np
import helper_functions as hf
import sys
import os
import time
import datetime


################################################################
# RUN PARAMETERS
lrs = np.logspace(-5,-3,7)
Ts = np.logspace(np.log10(1),np.log10(15),8)
alphas, step = np.linspace(0,0.75,2,retstep=True)
# lrs = np.array([1e-3])
# Ts = np.array([2])
# alphas = np.array([0, 0.6])
num_repeat = 5                      # could be 10?
batch_size = 50
num_epochs_tuning = 5                      # could be changed... 5? 10? 20? write_logits.py uses 20.
num_epochs_final = 5
hidden_sizes = [100, 100]           # could be increased when ready...


################################################################
# !!! SHOULD REVERSE THIS AT THE END OF THIS SCRIPT !!!
# Set up printing out a log (redirects all prints to the file)
log_timestamp = datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d_%H%M%S')
orig_stdout = sys.stdout
f_log_name = 'Results/' + os.path.basename(__file__) \
                        + '_' \
                        + log_timestamp \
                        + '.log'
logger = hf.Logger(f_log_name)
sys.stdout = logger


################################################################
# LOG THE RUN PARAMETERS
print '\nRUN PARAMETERS'
print 'lrs =', lrs
print 'Ts =', Ts
print 'alphas =', alphas
print 'num_repeat =', num_repeat
print 'batch_size =', batch_size
print 'num_epochs_tuning =', num_epochs_tuning
print 'num_epochs_final =', num_epochs_final
print 'hidden_sizes =', hidden_sizes
print '\n'


################################################################
# LOAD DATA

# Read train_logits
logits_cumbersome = np.loadtxt('Data/logits_mnist_tuned3.csv', delimiter=', ')

# Read input data
from tensorflow.examples.tutorials.mnist import input_data
mnist = input_data.read_data_sets('MNIST_data', one_hot=True)

# USE MNIST.VALIDATION AND MNIST.TEST AS USUAL
# BUT USE THE FOLLOWING TRUNCATED SET FOR TRAINING
truncated_size = 20000
mnist_train_truncated = mnist.train.next_batch(batch_size=truncated_size,shuffle=False)
logits_cumbersome = logits_cumbersome[:truncated_size]


################################################################
# NEURAL NETWORK

def simple_network(sess, y_soft, lr, T, alpha, batch_size, num_epochs, tensorboard=False):
    iters_per_epoch = mnist_train_truncated[0].shape[0] / batch_size

    alpha_tf = tf.Variable(alpha, trainable=False, dtype=tf.float64)
    T_tf = tf.Variable(T, trainable=False, dtype=tf.float64)

    if tensorboard:
        with tf.name_scope('input'):
            x = tf.placeholder(tf.float64, shape=[None, 784])
            y_soft_ = tf.placeholder(tf.float64, shape=[None, 10])
            y_hard_ = tf.placeholder(tf.float64, shape=[None, 10])

        h1, W1, b1 = hf.nn_layer(x,28*28,hidden_sizes[0],'fc1',act=tf.nn.relu,operation=tf.matmul)
        h2, W2, b2 = hf.nn_layer(h1,hidden_sizes[0],hidden_sizes[1],'fc2',act=tf.nn.relu,operation=tf.matmul)
        y_out, W3, b3 = hf.nn_layer(h2,hidden_sizes[1],10,'out',act=tf.identity,operation=tf.matmul)
    else:
        x = tf.placeholder(tf.float64, shape=[None, 784])
        y_soft_ = tf.placeholder(tf.float64, shape=[None, 10])
        y_hard_ = tf.placeholder(tf.float64, shape=[None, 10])

        W1 = hf.weight_variable([28 * 28, hidden_sizes[0]])
        b1 = hf.bias_variable([hidden_sizes[0]])
        h1 = tf.nn.relu(tf.matmul(x, W1) + b1)

        W2 = hf.weight_variable([hidden_sizes[0], hidden_sizes[1]])
        b2 = hf.bias_variable([hidden_sizes[1]])
        h2 = tf.nn.relu(tf.matmul(h1, W2) + b2)

        W3 = hf.weight_variable([hidden_sizes[1], 10])
        b3 = hf.bias_variable([10])
        y_out = tf.matmul(h2, W3) + b3

    y_out_soft = hf.softmax_T(y_out, T_tf, tensor=True)    # temperature softmax
    y_out_hard = hf.softmax_T(y_out, tf.Variable(1.0, trainable=False, dtype=tf.float64), tensor=True)         # temperature=1 softmax

    if tensorboard:
        with tf.name_scope('cross_entropy_soft'):
            with tf.name_scope('total'):
                cross_entropy_soft = tf.reduce_mean(-tf.reduce_sum(y_soft_ * tf.log(y_out_soft), reduction_indices=[1]))
                cross_entropy_soft = tf.add(tf.mul(tf.sub(tf.constant(1.0, dtype=tf.float64), tf.pow(T_tf, 2)),
                                                   tf.stop_gradient(cross_entropy_soft)),
                                            tf.mul(tf.pow(T_tf, 2), cross_entropy_soft))

            tf.scalar_summary('cross entropy soft', cross_entropy_soft)

        with tf.name_scope('cross_entropy_hard'):
            with tf.name_scope('total'):
                cross_entropy_hard = tf.reduce_mean(tf.neg(tf.reduce_sum(tf.mul(y_hard_, tf.log(y_out_hard)), reduction_indices=[1])))

            tf.scalar_summary('cross entropy hard', cross_entropy_hard)

        with tf.name_scope('cross_entropy'):
            # cross_entropy = tf.add((tf.mul(tf.pow(T_tf, 2), tf.mul(alpha_tf, cross_entropy_soft))),
            #                        (tf.mul(tf.sub(tf.constant(1.0,dtype=tf.float64),alpha_tf), cross_entropy_hard)))
            cross_entropy = tf.add((tf.mul(alpha_tf, cross_entropy_soft)),
                                   (tf.mul(tf.sub(tf.constant(1.0,dtype=tf.float64),alpha_tf), cross_entropy_hard)))
            tf.scalar_summary('cross entropy', cross_entropy)

        with tf.name_scope('accuracy'):
            with tf.name_scope('correct_prediction'):
                correct_prediction = tf.equal(tf.argmax(y_out_hard, 1), tf.argmax(y_hard_, 1))
            with tf.name_scope('accuracy'):
                accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float64))
            tf.scalar_summary('accuracy', accuracy)
    else:
        cross_entropy_soft = tf.reduce_mean(-tf.reduce_sum(y_soft_ * tf.log(y_out_soft), reduction_indices=[1]))
        cross_entropy_soft = tf.add(tf.mul(tf.sub(tf.constant(1.0, dtype=tf.float64), tf.pow(T_tf, 2)),
                                           tf.stop_gradient(cross_entropy_soft)),
                                    tf.mul(tf.pow(T_tf, 2), cross_entropy_soft))
        cross_entropy_hard = tf.reduce_mean(-tf.reduce_sum(y_hard_ * tf.log(y_out_hard), reduction_indices=[1]))
        # cross_entropy = tf.add((tf.mul(tf.pow(T_tf,2),tf.mul(alpha_tf,cross_entropy_soft))), (tf.mul(tf.sub(tf.constant(1.0,dtype=tf.float64),alpha_tf),cross_entropy_hard)))
        cross_entropy = tf.add((tf.mul(alpha_tf,cross_entropy_soft)), (tf.mul(tf.sub(tf.constant(1.0,dtype=tf.float64),alpha_tf),cross_entropy_hard)))
        # cross_entropy = (alpha * cross_entropy_soft) + ((1 - alpha) * cross_entropy_hard)


        # # Shifted below - train_step computation

        correct_prediction = tf.equal(tf.argmax(y_out_hard,1), tf.argmax(y_hard_,1))
        accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float64))


    # train_step = tf.train.AdamOptimizer(lr).minimize(cross_entropy)
    global_step = tf.Variable(0, trainable=False)
    learning_rate = tf.train.exponential_decay(lr, global_step, iters_per_epoch, 0.9, staircase=True)
    train_step = tf.train.AdamOptimizer(learning_rate).minimize(cross_entropy)

    if tensorboard:
        # Merge all the summaries and write them out to /tmp/mnist_logs (by default)
        merged = tf.merge_all_summaries()
        timestamp = datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d_%H%M%S')
        train_writer = tf.train.SummaryWriter('tensorboard_logs/mnist_simple_logs_' + timestamp + '/train',
                                            sess.graph)
        # Test writer actually logs validation accuracies
        val_writer = tf.train.SummaryWriter('tensorboard_logs/mnist_simple_logs_' + timestamp + '/val')

    sess.run(tf.global_variables_initializer())

    for i in range(num_epochs*iters_per_epoch):
        x_batch = mnist_train_truncated[0][(i%iters_per_epoch)*batch_size:((i%iters_per_epoch)+1)*batch_size]
        y_hard_batch = mnist_train_truncated[1][(i % iters_per_epoch) * batch_size:((i % iters_per_epoch) + 1) * batch_size]
        # if i % 10 == 0:
        #     print 'W1\t\tmax: %.3e\t\tmin: %.3e\t\tmean: %.3e' % (tf.reduce_max(W1).eval(), tf.reduce_min(W1).eval(), tf.reduce_mean(W1).eval())
        #     print 'W2\t\tmax: %.3e\t\tmin: %.3e\t\tmean: %.3e' % (tf.reduce_max(W2).eval(), tf.reduce_min(W2).eval(), tf.reduce_mean(W2).eval())
        #     print 'W3\t\tmax: %.3e\t\tmin: %.3e\t\tmean: %.3e' % (tf.reduce_max(W3).eval(), tf.reduce_min(W3).eval(), tf.reduce_mean(W3).eval())
        #     for gv in sess.run(grads_and_vars, feed_dict={x: batch[0],
        #                           y_soft_: y_soft[(i%iters_per_epoch)*batch_size:((i%iters_per_epoch)+1)*batch_size],
        #                           y_hard_: batch[1]}):
        #         print tf.reduce_max(gv[0]).eval(), tf.reduce_min(gv[0]).eval(), tf.reduce_mean(gv[0]).eval()
        # if i%1000 == 0:
        #     train_accuracy = accuracy.eval(feed_dict={x:batch[0], y_hard_: batch[1]})
        #     print("step %d, training accuracy %g"%(i, train_accuracy))
        #     if tensorboard:
        #         summary, train_accuracy = sess.run([merged,accuracy],feed_dict={x:batch[0], y_hard_: batch[1]})
        #         val_writer.add_summary(summary, i)
        #         print("step %d, training accuracy %g"%(i, train_accuracy))
        # if i%50 == 0:
        #     print 'val_acc: %.4f' % hf.accuracy_in_batches(mnist.validation, accuracy, x, y_hard_, batch_size=batch_size)

        if tensorboard:
            summary, _ = sess.run([merged, train_step],feed_dict={x: x_batch,
                                                                  y_soft_: y_soft[(i%iters_per_epoch)*batch_size:((i%iters_per_epoch)+1)*batch_size],
                                                                  y_hard_: y_hard_batch})
            train_writer.add_summary(summary, i)
        else:
            train_step.run(feed_dict={x: x_batch,
                                      y_soft_: y_soft[(i % iters_per_epoch) * batch_size:((
                                                                                          i % iters_per_epoch) + 1) * batch_size],
                                      y_hard_: y_hard_batch})

    if tensorboard:
        train_writer.close()
        val_writer.close()

    return x, y_hard_, accuracy


################################################################
# HYPERPARAMETER OPTIMIZATION
print '\nHyperparameter optimization...\n'

results_np = np.zeros([lrs.shape[0], Ts.shape[0], alphas.shape[0]])
# results_np_w_repeat = np.zeros([lrs.shape[0], Ts.shape[0], alphas.shape[0], num_repeat])

best_val_acc = None
best_lr = None
best_T = None
best_alpha = None

# Tensorflow stuff
lr_index = -1
for lr in lrs:
    lr_index += 1

    T_index = -1
    for T in Ts:
        T_index += 1

        y_soft = hf.softmax_T(logits_cumbersome, T)  # temperature softmax

        alpha_index = -1
        for alpha in alphas:
            alpha_index += 1

            avg_val_acc  = 0
            for repeat in range(num_repeat):
                tf.reset_default_graph()
                sess = tf.InteractiveSession()

                x, y_hard_, accuracy = simple_network(sess, y_soft, lr, T, alpha, batch_size, num_epochs_tuning)

                val_acc  = hf.accuracy_in_batches(mnist.validation, accuracy, x, y_hard_, batch_size=batch_size)
                avg_val_acc  += val_acc

                # results_np_w_repeat[lr_index, T_index, alpha_index, repeat] = val_acc

                sess.close()

            avg_val_acc /= num_repeat
            print 'lr: %.3e    T: %.4f    alpha: %.2f    val_acc: %.4f' % (lr, T, alpha, avg_val_acc)
            results_np[lr_index, T_index, alpha_index] = avg_val_acc

            if avg_val_acc > best_val_acc:
                best_val_acc = avg_val_acc
                best_lr = lr
                best_T = T
                best_alpha = alpha

print '\n\nbest_lr: %.3e    best_T: %.4f    best_alpha: %.2f    best_val_acc: %.4f' % (best_lr, best_T, best_alpha, best_val_acc)


np.savetxt('Results/results_np_'+log_timestamp+'.csv', results_np.reshape([lrs.shape[0], Ts.shape[0]*alphas.shape[0]]), delimiter=', ')
# np.savetxt('Results/results_np_w_repeat_'+log_timestamp+'.csv', results_np_w_repeat.reshape([lrs.shape[0], Ts.shape[0]*alphas.shape[0]*num_repeat]), delimiter=', ')


################################################################
# TRAIN A MODEL WITH OPTIMAL HYPERPARAMETERS FOR LONGER
print '\n\nTraining a model with optimal hyperparameters for', num_epochs_final, 'epochs...'

y_soft = hf.softmax_T(logits_cumbersome, best_T)  # temperature softmax

avg_train_acc = 0
avg_val_acc   = 0
avg_test_acc  = 0

for repeat in range(num_repeat):
    tf.reset_default_graph()
    sess = tf.InteractiveSession()

    x, y_hard_, accuracy = simple_network(sess, y_soft, best_lr, best_T, best_alpha, batch_size, num_epochs_final, tensorboard=True)

    avg_train_acc += hf.accuracy_in_batches_alt(mnist_train_truncated[0], mnist_train_truncated[1], accuracy, x, y_hard_, batch_size=batch_size)
    avg_val_acc   += hf.accuracy_in_batches(mnist.validation, accuracy, x, y_hard_, batch_size=batch_size)
    avg_test_acc  += hf.accuracy_in_batches(mnist.test, accuracy, x, y_hard_, batch_size=batch_size)

    sess.close()

avg_train_acc /= num_repeat
avg_val_acc   /= num_repeat
avg_test_acc  /= num_repeat

print '\n\nACCURACIES WITH A MODEL TRAINED WITH SOFT TARGETS'
print 'On training set:   %.4f' % avg_train_acc
print 'On validation set: %.4f' % avg_val_acc
print 'On test set:       %.4f' % avg_test_acc


print '\n\nTraining a model without soft targets for', num_epochs_final, 'epochs...'

y_soft = hf.softmax_T(logits_cumbersome, 1.0)  # temperature softmax

avg_train_acc = 0
avg_val_acc   = 0
avg_test_acc  = 0

for repeat in range(num_repeat):
    tf.reset_default_graph()
    sess = tf.InteractiveSession()

    x, y_hard_, accuracy = simple_network(sess, y_soft, best_lr, 1.0, 0.0, batch_size, num_epochs_final, tensorboard=True)

    avg_train_acc += hf.accuracy_in_batches_alt(mnist_train_truncated[0], mnist_train_truncated[1], accuracy, x, y_hard_, batch_size=batch_size)
    avg_val_acc   += hf.accuracy_in_batches(mnist.validation, accuracy, x, y_hard_, batch_size=batch_size)
    avg_test_acc  += hf.accuracy_in_batches(mnist.test, accuracy, x, y_hard_, batch_size=batch_size)

    sess.close()

avg_train_acc /= num_repeat
avg_val_acc   /= num_repeat
avg_test_acc  /= num_repeat

print '\n\nACCURACIES WITH A MODEL TRAINED WITHOUT SOFT TARGETS'
print 'On training set:   %.4f' % avg_train_acc
print 'On validation set: %.4f' % avg_val_acc
print 'On test set:       %.4f' % avg_test_acc


################################################################
# !!! RESETTING STDOUT LOGGING !!!
# Stop redirecting pring out to log
logger.close_log()
sys.stdout = orig_stdout
