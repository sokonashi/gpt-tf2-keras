import numpy as np
import argparse


import tensorflow as tf
from tensorflow import keras


from src.layers import EmbeddingSim, EmbeddingRet, PositionEmbedding, LayerNormalization, _get_encoder_component, gelu, ScaledDotProductAttention, MultiHeadAttention, FeedForward
from src import encoder
from src import net
from src import utils


parser = argparse.ArgumentParser(description='Input argument parser.')

parser.add_argument('--model_dir', type=str, help='path of model folder')

parser.add_argument('--custom_model', type=str, help='path to custom model')

parser.add_argument('--nucleus', help='flag to turn on/off nucleus sampling', action='store_true')

parser.add_argument('--top_p', type=float, help='cut off probablity for nucleus sampling',
					default=1.0)

parser.add_argument('--top_k', type=int, help='cut off ranking for top K sampling',
					default=2)

parser.add_argument('--temperature', type=float, help='temperature in text generation. Higher temperature creates more randomness in the results.',
					default=1.0)

parser.add_argument('--batch_size', type=int, help='batch size, for use with multi-GPUs',
					default=2)

parser.add_argument('--output_length', type=int, help='length of output sequence (number of tokens)',
					default=100)

parser.add_argument('--starter', type=str, help='starter sentence')

args = parser.parse_args()


def main():
	if not args.model_dir:
		print('model path must be provided.')
		print('quit program.')
		exit()
	
	if args.custom_model:
		args.model_path = args.custom_model
	else:
		args.model_path = args.model_dir + "model.ckpt"

	args.json_hparams = args.model_dir + "hparams.json"
	args.json_encoder = args.model_dir + "encoder.json"
	args.vocab_bpe = args.model_dir + "vocab.bpe"

	args.starter = args.starter.replace("\\n", "\n")
	args.starter = args.starter.replace("\\'", "'")

	print()
	
	enc = encoder.get_encoder(args.json_encoder, args.vocab_bpe)

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

	# prepare input data
	input_data = [enc.encode(args.starter)] * args.batch_size    
	start_length = [len(data) for data in input_data]
	flag_stop = [False] * args.batch_size
	stop = False
		
	# run inference
	for shift in range(args.output_length):
		output_data = model.predict(np.array(input_data), batch_size=2)
		for index in range(args.batch_size):
			if not flag_stop[index]:
				probs = [(prob, i) for i, prob in enumerate(output_data[index, start_length[index] + shift - 1])]
				probs.sort(reverse=True)
				if args.nucleus:
					next_token = utils.find_top_p(probs, args.top_p, args.temperature)
				else:
					next_token = utils.find_top_p(probs, args.top_k, args.temperature)
				input_data[index].append(next_token)
				if next_token == 50256:
					flag_stop[index] = True
			else:
				input_data[index].append(50256)
			
			output = enc.decode(input_data[index])
			if '\n' in output:
				stop = True
		
		if stop:
			break
			
	print(output)
	
if __name__ == '__main__':
	main()
