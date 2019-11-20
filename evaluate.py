import numpy as np
import argparse
import importlib


import tensorflow as tf
from tensorflow import keras


from src.layers import EmbeddingSim, EmbeddingRet, PositionEmbedding, LayerNormalization, _get_encoder_component, gelu, ScaledDotProductAttention, MultiHeadAttention, FeedForward
from src import encoder
from src import net
from src import utils


parser = argparse.ArgumentParser(description='Input argument parser.')

parser.add_argument('--model_path', type=str, help='path of model')

parser.add_argument('--task', type=str, help='name of task',
					choices=['cnndm', 'coqa'])

parser.add_argument('--json_hparams', type=str, help='path to the json of hyper parameters')

parser.add_argument('--json_encoder', type=str, help='path to the json of encoder')

parser.add_argument('--dataset_path', type=str, help='path to dataset')

parser.add_argument('--data_loader', type=str, help='type of dataset',
                    choices=['text', 'cnndm', 'coqa'])

parser.add_argument('--length', type=int, help='length of input sequence (number of tokens)',
                    default=1024)

parser.add_argument('--vocab_bpe', type=str, help='path to the vocabulary bpe')

parser.add_argument('--eager', help='flag to turn on/off eager mode', action='store_true')

parser.add_argument('--nucleus', help='flag to turn on/off nucleus sampling', action='store_true')

parser.add_argument('--top_p', type=float, help='cut off probablity for nucleus sampling',
                    default=1.0)

parser.add_argument('--top_k', type=int, help='cut off ranking for top K sampling',
                    default=2)

parser.add_argument('--temperature', type=float, help='temperature in text generation. Higher temperature creates more randomness in the results.',
                    default=1.0)

parser.add_argument('--batch_size', type=int, help='batch size',
                    default=1)

parser.add_argument('--output_length', type=int, help='length of output sequence (number of tokens)',
                    default=100)

args = parser.parse_args()


def main():

    if not args.eager:
        tf.compat.v1.disable_eager_execution()

    if not args.json_encoder:
        print('json_encoder must be provided.')
        print('quit program.')
        exit()

    if not args.vocab_bpe:
        print('vocab.bpe must be provided.')
        print('quit program.')
        exit()

    enc = encoder.get_encoder(args.json_encoder, args.vocab_bpe)

    ds = importlib.import_module(
        "src.load_" + args.data_loader).create_dataset(
        'test', enc, args.length, args.dataset_path, args.batch_size,
        output_length=args.output_length)

    # for value in ds.take(10):
    #     x = enc.decode(value[0].numpy())
    #     print(x)
    #     print(len(value[0]))
    #     input("Press Enter to continue...")

    # exit()

    # load model
    if args.model_path.split('.')[-1] == 'h5':
        model = keras.models.load_model(
            args.model_path,
            custom_objects={'EmbeddingSim': EmbeddingSim,
                            'EmbeddingRet': EmbeddingRet,
                            'PositionEmbedding': PositionEmbedding,
                            'LayerNormalization': LayerNormalization,
                            'ScaledDotProductAttention': ScaledDotProductAttention,
                            'MultiHeadAttention': MultiHeadAttention,
                            'FeedForward': FeedForward,
                            'gelu': gelu,
                            'loss': net.loss})
    elif args.model_path.split('.')[-1] == 'ckpt':
        args.model_ckpt = args.model_path
        model = net.create_model(args)
        model = net.load_weights(model, args)
        model.compile(
            optimizer=keras.optimizers.Adam(),
            loss=net.loss
        )
    else:
        print('Unrecognized model format: ' + args.model_path.split('.')[-1])
        exit()

    model.trainable = False    

    num_sample = 3

    for value in ds.take(10):
        input_data = [np.array(value[0]).tolist() for i in range(num_sample)]
        start_length = [len(value[0]) for data in input_data]
        flag_stop = [False for i in range(num_sample)]


        for shift in range(args.output_length):
            output_data = model.predict(np.array(input_data))
            
            for index in range(num_sample):

                if not flag_stop[index]:
                    probs = [(prob, i) for i, prob in enumerate(output_data[index, start_length[index] + shift - 1])]
                    probs.sort(reverse=True)
                    
                    if args.nucleus:
                        next_token = utils.find_top_p(probs, args.top_p, args.temperature)
                    else:
                        next_token = utils.find_top_k(probs, args.top_k, args.temperature)

                    input_data[index].append(next_token)

                    if next_token == 50256:
                        flag_stop[index] = True
                else:
                    input_data[index].append(50256)

        # print result
        for index in range(num_sample):
            output = enc.decode(input_data[index])
            print(output)
            print('--------------------------------------------------')

        print('===================================================================================')

    #     output = model.predict(ds, steps=1)
    #     for shift in range(args.output_length):
            
    #     # print(output)
        

if __name__ == '__main__':
    main()