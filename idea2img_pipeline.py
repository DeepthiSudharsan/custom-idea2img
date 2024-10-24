### Set up environment variables:
import os
import time
import argparse
import csv, json
import cv2, base64
from tqdm import tqdm
import requests
import random
import torch
# from datetime import datetime
from PIL import Image

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential

load_dotenv()

managed_identity_client_id = os.environ.get("MANAGED_IDENTITY_CLIENT_ID")
openai_endpoint = os.environ.get("OPENAI_ENDPOINT")

token_credential = DefaultAzureCredential(managed_identity_client_id=managed_identity_client_id)

token = token_credential.get_token('https://cognitiveservices.azure.com/.default')

def gptv_query(transcript=None, temp=0.):
    max_tokens = 512
    wait_time = 10

    for x in range(len(transcript)):
        message = transcript[x]
        new_content = []
        for content in message["content"]:
            if type(content) == str:
                new_content.append({
                    "type": "text",
                    "text": content
                })
            else:
                new_content.append(content)
        message["content"] = new_content

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token.token}"
    }
    data = {
        'model': 'gpt-4o',
        'max_tokens':max_tokens, 
        'temperature': temp,
        'top_p': 0.5,
        'messages':[]
    }
    if transcript is not None:
        data['messages'] = transcript

    response_text, retry, response_json = '', 0, None
    while len(response_text)<2:
        retry += 1
        try:
            response = requests.post(openai_endpoint, headers=headers, data=json.dumps(data)) 
            response_json = response.json()
        except Exception as e:
            if random.random()<1: print(e)
            time.sleep(wait_time)
            continue
        if response.status_code != 200:
            if random.random()<0.01: print(f"The response status code for is {response.status_code} (Not OK)")
            time.sleep(wait_time)
            data['temperature'] = min(data['temperature'] + 0.2, 1.0)
            continue
        if 'choices' not in response_json:
            time.sleep(wait_time)
            continue
        response_text = response_json["choices"][0]["message"]["content"]
        print(response_text)
    return response_json["choices"][0]["message"]["content"]

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def load_img(image_path):
    base64_image = encode_image(image_path)
    image_meta = "data:image/png;base64" if 'png' in image_path else "data:image/jpeg;base64"
    img_dict = {
        "type": "image_url",
        "image_url": {
          "url": f"{image_meta},{base64_image}",
          "detail": "low"
        }
    }
    return img_dict

def prepare_fewshot_textreflection(user_prompt, img_prompt, round_best, listofimages, image_history, prompt_history, reflection_history, args):
    transcript = []
    transcript.append("Here are some examples:\n")
    ## Example 1
    transcript.append("IDEA: photo of a dog looks like the one in the given image on the grass, but change the dog color to blue and remove the carrot.")
    transcript.append(load_img("input_img/dog2.jpg"))
    transcript.append("End of IDEA.")
    transcript.append("Generated sentence prompt for current round is: A cheerful blue dog with a big grin on its face, sitting on the grass with a blurred background of purple flowers, wagging its tail energetically.\nCorresponding image generated by the AI art generation model:")
    transcript.append(load_img("input_img/example_1.png"))
    transcript.append("Based on the above information, I wrote REASON that is wrapped with <START> and <END>.\n REASON: ")
    transcript.append("<START> The dog in the generated image is not in the blue color, and does not look like the one in the given image. The dog in the given image is a white Labrador Retriever, while the dog in the generated image is a shetland sheepdog. To address this issue, the sentence prompt should be modified to specifically mention the breed of the dog as a Labrador Retriever, and the dog is in the blue color. <END>.\n")
    transcript.append("\n\n###\n\n")

    ## Example 2
    transcript.append("IDEA: a person practicing yoga boat pose at beach with no boats nearby.")
    transcript.append("End of IDEA.")
    transcript.append("Generated sentence prompt for current round is: A person balancing in yoga boat pose on a peaceful beach with a clear blue sky and palm trees, no boats in sight.\nCorresponding image generated by the AI art generation model:")
    transcript.append(load_img("input_img/example_2.png"))
    transcript.append("Based on the above information, I wrote REASON that is wrapped with <START> and <END>.\n REASON: ")
    transcript.append("<START> The person in the image is not balancing in yoga boat pose, but in a different yoga pose. Because the prompt has already mention boat pose, the AI art model might not understand what is boat pose. To address this, the sentence prompt should be modified to specifically mention what is a boat pose: posture where one balances on the sit bones with legs and upper body lifted, forming a V shape with the body. <END>.\n")
    transcript.append("\n\n###\n\n")

    ## Example 3
    transcript.append("IDEA: Photo of Bill Gates with the same cloth, background, and hand gesture as in the given image with a pug dog next to him.")
    transcript.append(load_img("input_img/person4.png"))
    transcript.append("End of IDEA.")
    transcript.append("Generated sentence prompt for current round is: Bill Gates in a suit, raising his hand in the same gesture as the given image, with a pug dog with big eyes standing next to him.\nCorresponding image generated by the AI art generation model:")
    transcript.append(load_img("input_img/example_3.png"))
    transcript.append("Based on the above information, I wrote REASON that is wrapped with <START> and <END>.\n REASON: ")
    transcript.append("<START> Bill Gates in the generated image has a different pose as in the given image. This is because the prompt mentions 'as the given image' but the AI art model can not understand image inputs. To address this, the sentence prompt should be modified to specifically mention the gesture in the given image is 'with his right hand raised in a friendly wave with his palm facing forward'. <END>.\n")
    transcript.append("\n\n###\n\n")

    ## Example 4
    transcript.append("IDEA: 8 apples on the table.")
    transcript.append("End of IDEA.")
    transcript.append("Generated sentence prompt for current round is: A black table with 8 pink apples scattered randomly, with a light blue background and a surreal style.\nCorresponding image generated by the AI art generation model:")
    transcript.append(load_img("input_img/example_4.png"))
    transcript.append("Based on the above information, I wrote REASON that is wrapped with <START> and <END>.\n REASON: ")
    transcript.append("<START> The image generated by the AI art generation model does not follow the user imagined IDEA of the scene as there are only 12 apples in the image instead of 8. To address this, the sentence prompt can be modified to specify that there should be 8 apples on the table, such as in one row with exactly 8 apples. <END>.\n")
    transcript.append("\n\n###\n\n")

    transcript.append("(END OF EXAMPLES)]\n Here is the sample to analyze:\n")
    return transcript

def prepare_fewshot_selectbest(user_prompt, img_prompt, listofimages, args):
    transcript = []

    transcript.append("Here are some examples:\n")
    ## Example 1
    transcript.append("IDEA: photo of a dog looks like the one in the given image on the grass, but change the dog color to blue and remove the carrot.")
    transcript.append(load_img("input_img/dog2.jpg"))
    transcript.append("End of IDEA.")
    transcript.append('0. ')
    transcript.append(load_img("input_img/example_1.png"))
    transcript.append('1. ')
    transcript.append(load_img("input_img/selectexample_1_3.png"))
    transcript.append("Image 0: The dog in the given image is a white Labrador Retriever, while the dog in the generated image is a shetland sheepdog. Furthermore, the generated dog is in white and pink, not blue described in IDEA. Overall score: 3. \n\n Image 1: The dog and grass are present, the dog looks like the one in the given image and is in the blue color. The image follows the content in IDEA, but the dog's color could be enhanced to a more vibrant blue. Overall score: 9.")
    transcript.append("\n\n###\n\n")

    ## Example 2
    transcript.append("IDEA: Photo of Bill Gates with the same cloth, background, and hand gesture as in the given image with a pug dog next to him.")
    transcript.append(load_img("input_img/person4.png"))
    transcript.append("End of IDEA.")
    transcript.append('2. ')
    transcript.append(load_img("input_img/example_3.png"))
    transcript.append("Image 2: Bill Gates in the generated image has a different pose as in the given image. The generated pose is waving right hand, but the correct pose is 'with his right hand raised in a friendly wave with his palm facing forward'.  Overall score: 6.")
    transcript.append("\n\n###\n\n")

    transcript.append("(END OF EXAMPLES)]\n Here is the sample to analyze:\n")
    return transcript


def gptv_init_prompt(user_prompt, img_prompt, idea_transcript, args):
    transcript = [{ "role": "system", "content": [] }, {"role": "user", "content": []}]
    # System prompt
    transcript[0]["content"].append("You are a helpful assistant.\n\nInstruction: Given a user imagined IDEA of the scene, converting the IDEA into a self-contained sentence prompt that will be used to generate an image.\n")
    transcript[0]["content"].append("Here are some rules to write good prompts:\n")
    transcript[0]["content"].append("- Each prompt should consist of a description of the scene followed by modifiers divided by commas.\n- The modifiers should alter the mood, style, lighting, and other aspects of the scene.\n- Multiple modifiers can be used to provide more specific details.\n- When generating prompts, reduce abstract psychological and emotional descriptions.\n- When generating prompts, explain images and unusual entities in IDEA with detailed descriptions of the scene.\n- Do not mention 'given image' in output, use detailed texts to describe the image in IDEA instead.\n- Generate diverse prompts.\n- Each prompt should have no more than 50 words.\n")

    ## Example & Query prompt
    transcript[-1]["content"] = transcript[-1]["content"] + idea_transcript
    transcript[-1]["content"].append("Based on the above information, you will write %d detailed prompts exactly about the IDEA follow the rules. Each prompt is wrapped with <START> and <END>.\n"%args.num_prompt)

    response = gptv_query(transcript)
    if '<START>' not in response or '<END>' not in response: ## one format retry
        response = gptv_query(transcript, temp=0.1)
    if args.verbose:
        print('gptv_init_prompt    IDEA: %s.\n %s\n'%(user_prompt,response))
    prompts = response.split('<START>')[1:]
    prompts = [x.strip().split('<END>')[0] for x in prompts]
    return prompts

def gptv_reflection_prompt_selectbest(user_prompt, img_prompt, idea_transcript, listofimages, args):
    num_img = len(listofimages)
    transcript = [{ "role": "system", "content": [] }, {"role": "user", "content": []}]
    # System prompt
    transcript[0]["content"].append("You are a helpful assistant.\n\nYou are a judge to rank provided images. Below are %d images generated by an AI art generation model, indexed from 0 to %d."%(num_img,num_img-1))
    transcript[0]["content"].append("From scale 1 to 10, decide how similar each image is to the user imagined IDEA of the scene.")

    ## Example & Query prompt
    if args.select_fewshot:
        transcript[-1]["content"] = transcript[-1]["content"] + prepare_fewshot_selectbest(user_prompt, img_prompt, listofimages, args)

    transcript[-1]["content"] = transcript[-1]["content"] + idea_transcript
    for img_i in range(num_img):
        transcript[-1]["content"].append("%d. "%img_i)
        transcript[-1]["content"].append(load_img(listofimages[img_i]))

    transcript[-1]["content"].append("Let's think step by step. Check all aspects to see how well these images strictly follow the content in IDEA, including having correct object counts, attributes, entities, relationships, sizes, appearance, and all other descriptions in the IDEA. Then give a score for each input images. Finally, consider the scores and select the image with the best overall quality with image index 0 to %d wrapped with <START> and <END>. Only wrap single image index digits between <START> and <END>."%(num_img-1))

    response = gptv_query(transcript)
    if '<START>' not in response or '<END>' not in response: ## one format retry
        response = gptv_query(transcript, temp=0.1)
    if args.verbose:
        print('gptv_reflection_prompt_selectbest\n %s\n'%(response))
    if '<START>' not in response or '<END>' not in response:
        return random.randint(0,num_img-1), response
    prompts = response.split('<START>')[1]
    prompts = prompts.strip().split('<END>')[0]
    return int(prompts) if prompts.isdigit() else random.randint(0,num_img-1), response

def gptv_reflection_prompt_textreflection(user_prompt, img_prompt, idea_transcript, round_best, listofimages, image_history, prompt_history, reflection_history, args):
    current_round = len(image_history)
    transcript = [{ "role": "system", "content": [] }, {"role": "user", "content": []}]
    # System prompt
    transcript[0]["content"].append("You are a helpful assistant.\n\nYou are iteratively refining the sentence prompt by analyzing the images produced by an AI art generation model, seeking to find out the differences between the user imagined IDEA of the scene and the actual output.\n")
    transcript[0]["content"].append("If the generated image is not perfect, provide key REASON on ways to improve the image and sentence prompt to better follow the user imagined IDEA of the scene. Here are some rules to write good key REASON:\n")
    transcript[0]["content"].append("- Carefully compare the current image with the IDEA to strictly follow the details described in the IDEA, including object counts, attributes, entities, relationships, sizes, and appearance. Write down what is different in detail.\n- Avoid hallucinating information or asks that is not mentioned in IDEA.\n- Explain images and unusual entities in IDEA with detailed text descriptions of the scene.\n- Explain how to modify prompts to address the given reflection reason.\n- Focus on one thing to improve in each REASON. \n- Avoid generating REASON identical with the REASON in previous rounds.\n")
    ## Example & Query prompt
    if args.fewshot:
        transcript[-1]["content"] = transcript[-1]["content"] + prepare_fewshot_textreflection(user_prompt, img_prompt, round_best, listofimages, image_history, prompt_history, reflection_history, args)
    transcript[-1]["content"] = transcript[-1]["content"] + idea_transcript

    transcript[-1]["content"].append("This is the round %d of the iteration.\n")
    if current_round!=1:
        transcript[-1]["content"].append("The iteration history are:\n")
        for rounds in range(0,len(image_history)-1):
            transcript[-1]["content"].append("Round %d:\nGenerated sentence prompt: %s\nCorresponding image generated by the AI art generation model:"%(rounds+1,prompt_history[rounds]))
            transcript[-1]["content"].append(load_img(image_history[rounds]))
            transcript[-1]["content"].append("However, %s."%(reflection_history[rounds]))
    transcript[-1]["content"].append("Generated sentence prompt for current round %d is: %s\nCorresponding image generated by the AI art generation model:"%(current_round,prompt_history[-1]))
    transcript[-1]["content"].append(load_img(image_history[-1]))

    transcript[-1]["content"].append("Based on the above information, you will write REASON that is wrapped with <START> and <END>.\n REASON: ")

    response = gptv_query(transcript)
    if '<START>' not in response or '<END>' not in response: ## one format retry
        response = gptv_query(transcript, temp=0.1)
    if args.verbose:
        print('gptv_reflection_prompt_textreflection\n %s\n'%(response))
    # return response
    if '<START>' not in response or '<END>' not in response:
        return response
    prompts = response.split('<START>')[1]
    prompts = prompts.strip().split('<END>')[0]
    return prompts

def gptv_revision_prompt(user_prompt, img_prompt, idea_transcript, image_history, prompt_history, reflection_history, args):
    current_round = len(image_history)
    transcript = [{ "role": "system", "content": [] }, {"role": "user", "content": []}]
    # System prompt
    transcript[0]["content"].append("You are a helpful assistant.\n\nInstruction: Given a user imagined IDEA of the scene, converting the IDEA into a sentence prompt that will be used to generate an image.\n")
    transcript[0]["content"].append("Here are some rules to write good prompts:\n")
    transcript[0]["content"].append("- Each prompt should consist of a description of the scene followed by modifiers divided by commas.\n- The modifiers should alter the mood, style, lighting, spatial details, and other aspects of the scene.\n- Multiple modifiers can be used to provide more specific details.\n- When generating prompts, reduce abstract psychological and emotional descriptions.\n- When generating prompts, explain images and unusual entities in IDEA with detailed descriptions of the scene.\n- Do not mention 'given image' in output, use detailed texts to describe the image in IDEA.\n- Generate diverse prompts.\n- Output prompt should have less than 50 words.\n")
    ## Example & Query prompt
    transcript[-1]["content"] = transcript[-1]["content"] + idea_transcript
    transcript[-1]["content"].append("You are iteratively improving the sentence prompt by looking at the images generated by an AI art generation model and find out what is different from the given IDEA.\n")
    transcript[-1]["content"].append("This is the round %d of the iteration.\n"%current_round)
    if current_round!=1:
        transcript[-1]["content"].append("The iteration history are:\n")
        for rounds in range(0,len(image_history)-1):
            transcript[-1]["content"].append("Round %d:\nGenerated sentence prompt: %s\nCorresponding image generated by the AI art generation model:"%(rounds+1,prompt_history[rounds]))
            transcript[-1]["content"].append(load_img(image_history[rounds]))
            transcript[-1]["content"].append("However, %s."%(reflection_history[rounds]))
    transcript[-1]["content"].append("Generated sentence prompt for current round %d is: %s\nCorresponding image generated by the AI art generation model:"%(current_round,prompt_history[-1]))
    transcript[-1]["content"].append(load_img(image_history[-1]))
    transcript[-1]["content"].append("However, %s."%(reflection_history[-1]))

    transcript[-1]["content"].append("Based on the above information, to improve the image, you will write %d detailed prompts exactly about the IDEA follow the rules. Make description of the scene more detailed and add modifiers to address the given key reasons to improve the image. Avoid generating prompts identical with the ones in previous rounds. Each prompt is wrapped with <START> and <END>.\n"%args.num_prompt)
    response = gptv_query(transcript)
    if '<START>' not in response or '<END>' not in response: ## one format retry
        response = gptv_query(transcript, temp=0.1)
    if args.verbose:
        print('gptv_revision_prompt    IDEA: %s.\n %s\n'%(user_prompt,response))
    prompts = response.split('<START>')[1:]
    prompts = [x.strip().split('<END>')[0] for x in prompts]
    while len(prompts)<args.num_prompt:
        prompts = prompts + ['blank image']
    return prompts

class t2i_sd3():
    def __init__(self, refiner=False, img2img=True):
        from diffusers import StableDiffusion3Pipeline, DiffusionPipeline
        self.refiner = refiner
        self.img2img = img2img
        self.pipe = StableDiffusion3Pipeline.from_pretrained("stabilityai/stable-diffusion-3-medium-diffusers", torch_dtype=torch.float16, use_safetensors=True, variant="fp16")
        # self.pipe.to("cuda")
        self.pipe.enable_model_cpu_offload()
        self.pipe.enable_xformers_memory_efficient_attention()
        self.pipe.set_progress_bar_config(disable=True)
        if self.refiner:
            self.refine_pipe = DiffusionPipeline.from_pretrained("stabilityai/stable-diffusion-xl-refiner-1.0",text_encoder_2=self.pipe.text_encoder_2,vae=self.pipe.vae,torch_dtype=torch.float16,use_safetensors=True,variant="fp16",)
            # self.pipe.to("cuda")
            self.refine_pipe.enable_model_cpu_offload()
            self.refine_pipe.enable_xformers_memory_efficient_attention()
            self.refine_pipe.set_progress_bar_config(disable=True)
        if self.img2img:
            # from diffusers import StableDiffusionXLImg2ImgPipeline
            self.img2img_pipe = StableDiffusion3Pipeline.from_pretrained("stabilityai/stable-diffusion-3-medium-diffusers", torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
            # self.pipe.to("cuda")
            self.img2img_pipe.enable_model_cpu_offload()
            self.img2img_pipe.enable_xformers_memory_efficient_attention()
            self.img2img_pipe.set_progress_bar_config(disable=True)            

    def inference(self,prompt,savename):
        image = self.pipe(prompt,output_type="latent").images[0]
        if self.refiner:
            image = self.refine_pipe(prompt=prompt, image=image[None, :]).images[0]
        image.save(savename)
    def img2img_inference(self,image,prompt,savename,strength=1.0):
        image = self.img2img_pipe(prompt=prompt, image=image, strength=strength, output_type="latent").images[0]
        if self.refiner:
            image = self.refine_pipe(prompt=prompt, image=image[None, :]).images[0]
        image.save(savename)

class t2i_fluxdev():
    def __init__(self, refiner=False, img2img=True):
        from diffusers import FluxPipeline
        self.refiner = refiner
        self.img2img = img2img
        self.pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-dev", torch_dtype=torch.float16, use_safetensors=True, variant="fp16")
        # self.pipe.to("cuda")
        self.pipe.enable_model_cpu_offload()
        self.pipe.enable_xformers_memory_efficient_attention()
        self.pipe.set_progress_bar_config(disable=True)
        # if self.refiner:
        #     self.refine_pipe = DiffusionPipeline.from_pretrained("stabilityai/stable-diffusion-xl-refiner-1.0",text_encoder_2=self.pipe.text_encoder_2,vae=self.pipe.vae,torch_dtype=torch.float16,use_safetensors=True,variant="fp16",)
        #     # self.pipe.to("cuda")
        #     self.refine_pipe.enable_model_cpu_offload()
        #     self.refine_pipe.enable_xformers_memory_efficient_attention()
        #     self.refine_pipe.set_progress_bar_config(disable=True)
        if self.img2img:
            from diffusers import FluxPipeline
            self.img2img_pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-dev", torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
            # self.pipe.to("cuda")
            self.img2img_pipe.enable_model_cpu_offload()
            self.img2img_pipe.enable_xformers_memory_efficient_attention()
            self.img2img_pipe.set_progress_bar_config(disable=True)            

    def inference(self,prompt,savename):
        image = self.pipe(prompt,output_type="latent").images[0]
        if self.refiner:
            image = self.refine_pipe(prompt=prompt, image=image[None, :]).images[0]
        image.save(savename)
    def img2img_inference(self,image,prompt,savename,strength=1.0):
        image = self.img2img_pipe(prompt=prompt, image=image, strength=strength, output_type="latent").images[0]
        if self.refiner:
            image = self.refine_pipe(prompt=prompt, image=image[None, :]).images[0]
        image.save(savename)
class t2i_sdxl():
    def __init__(self, refiner=False, img2img=True):
        from diffusers import DiffusionPipeline
        self.refiner = refiner
        self.img2img = img2img
        self.pipe = DiffusionPipeline.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", torch_dtype=torch.float16, use_safetensors=True, variant="fp16")
        # self.pipe.to("cuda")
        self.pipe.enable_model_cpu_offload()
        self.pipe.enable_xformers_memory_efficient_attention()
        self.pipe.set_progress_bar_config(disable=True)
        if self.refiner:
            self.refine_pipe = DiffusionPipeline.from_pretrained("stabilityai/stable-diffusion-xl-refiner-1.0",text_encoder_2=self.pipe.text_encoder_2,vae=self.pipe.vae,torch_dtype=torch.float16,use_safetensors=True,variant="fp16",)
            # self.pipe.to("cuda")
            self.refine_pipe.enable_model_cpu_offload()
            self.refine_pipe.enable_xformers_memory_efficient_attention()
            self.refine_pipe.set_progress_bar_config(disable=True)
        if self.img2img:
            from diffusers import StableDiffusionXLImg2ImgPipeline
            self.img2img_pipe = StableDiffusionXLImg2ImgPipeline.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
            # self.pipe.to("cuda")
            self.img2img_pipe.enable_model_cpu_offload()
            self.img2img_pipe.enable_xformers_memory_efficient_attention()
            self.img2img_pipe.set_progress_bar_config(disable=True)            

    def inference(self,prompt,savename):
        image = self.pipe(prompt,output_type="latent").images[0]
        if self.refiner:
            image = self.refine_pipe(prompt=prompt, image=image[None, :]).images[0]
        image.save(savename)
    def img2img_inference(self,image,prompt,savename,strength=1.0):
        image = self.img2img_pipe(prompt=prompt, image=image, strength=strength, output_type="latent").images[0]
        if self.refiner:
            image = self.refine_pipe(prompt=prompt, image=image[None, :]).images[0]
        image.save(savename)

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--api_key", type=str, help="OpenAI GPT-4V API key; https://platform.openai.com/docs/guides/vision")
    # parser.add_argument("--huggingface_key", type=str, help="huggingface SD3 key")
    parser.add_argument("--testfile", type=str, default="testsample.txt")
    parser.add_argument("--num_img", type=int, default=1, help="number of images to generate per prompt")
    parser.add_argument("--num_prompt", type=int, default=3, help="number of prompts to search each round")
    parser.add_argument("--max_rounds", type=int, default=3, help="max number of iter rounds")
    parser.add_argument("--verbose", default=False, action="store_true")
    parser.add_argument("--foldername", type=str, default="sd3_iter")
    parser.add_argument("--strength", type=float, default=1.00, help="strength of img2img pipeline")
    parser.add_argument("--fewshot", default=False, action="store_true")
    parser.add_argument("--select_fewshot", default=False, action="store_true")
    parser.add_argument("--img2img", default=False, action="store_true", help="if use SD3 img2img pipeline, instead of SD3 T2I. Both with refiner in default.")
    args = parser.parse_args()
    assert(args.num_img==1)

    # from huggingface_hub import login
    # access_token_write = args.huggingface_key
    # login(token = access_token_write)

    # global api_key
    # api_key = args.api_key

    os.system('mkdir -p output/%s'%args.foldername)
    os.system('mkdir -p output/%s/iter'%args.foldername)
    os.system('mkdir -p output/%s/round1'%args.foldername)
    os.system('mkdir -p output/%s/iter_best'%args.foldername)
    os.system('mkdir output/%s/tmp'%args.foldername)

    sample_list = [x.strip() for x in list(open(args.testfile,'r'))]
    # t2i_model = t2i_sd15()
    t2i_model = t2i_sdxl(refiner=True, img2img=True)

    for sample_ii in tqdm(range(len(sample_list))):
        user_prompt, img_prompt = sample_list[sample_ii], None
        prompt_list = user_prompt.split('<IMG>')
        user_prompt = user_prompt.split('<IMG>')[0] ## legacy, for naming use only
        idea_transcript = []
        for ii in range(len(prompt_list)):
            if ii == 0:
                idea_transcript.append("IDEA: %s."%prompt_list[0])
            elif ii%2==1:
                idea_transcript.append(load_img(prompt_list[ii]))
            elif ii%2==0:
                idea_transcript.append("%s"%prompt_list[ii])
        idea_transcript.append("End of IDEA.\n")

        text_record = 'output/%s/tmp/%s.txt'%(args.foldername,user_prompt.replace(' ','').replace('.',''))
        os.system('mkdir output/%s/tmp/%s'%(args.foldername,user_prompt.replace(' ','').replace('.','')))

        ### GPTV prompting iter
        current_prompts, prompt_history, select_history, image_history, reflection_history, bestidx_history = [],[],[],[],[],[]
        for rounds in range(args.max_rounds):
            if args.verbose: print('ROUND %d:\n'%rounds)
            ###### new rounds' prompt (init/revision)
            if rounds == 0:
                gptv_prompts = gptv_init_prompt(user_prompt, None, idea_transcript, args)
            else:
                gptv_prompts = gptv_revision_prompt(user_prompt, None, idea_transcript, image_history, prompt_history, reflection_history, args)
            current_prompts = gptv_prompts
            ###### t2i generation
            for ii in range(args.num_prompt):
                for jj in range(args.num_img):
                    if args.img2img:
                        if '<IMG>' in sample_list[sample_ii]:
                            t2i_model.img2img_inference(Image.open(sample_list[sample_ii].split('<IMG>')[1]).resize((1024,1024)), gptv_prompts[ii],'output/%s/tmp/%s/%d_%d_%d.png'%(args.foldername,user_prompt.replace(' ','').replace('.',''),rounds,ii,jj),strength=args.strength)
                        else:
                            t2i_model.inference(gptv_prompts[ii],'output/%s/tmp/%s/%d_%d_%d.png'%(args.foldername,user_prompt.replace(' ','').replace('.',''),rounds,ii,jj))
                    else: ## T2I
                        t2i_model.inference(gptv_prompts[ii],'output/%s/tmp/%s/%d_%d_%d.png'%(args.foldername,user_prompt.replace(' ','').replace('.',''),rounds,ii,jj))
            ###### reflection: first select best, then give reason to improve (i.e., reflection)
            round_best, select_response = gptv_reflection_prompt_selectbest(user_prompt, img_prompt, idea_transcript, ['output/%s/tmp/%s/%d_%d_0.png'%(args.foldername,user_prompt.replace(' ','').replace('.',''),rounds,ii) for ii in range(args.num_prompt)], args)
            ## select the best, give an index. two separate calls
            prompt_history.append(current_prompts[round_best])
            select_history.append('Round selection: %d. || '%round_best+select_response)
            image_history.append('output/%s/tmp/%s/%d_%d_0.png'%(args.foldername,user_prompt.replace(' ','').replace('.',''),rounds,round_best))
            bestidx_history.append(round_best)
            if rounds!=args.max_rounds-1:
                reflection_text = gptv_reflection_prompt_textreflection(user_prompt, img_prompt, idea_transcript, round_best, ['output/%s/tmp/%s/%d_%d_0.png'%(args.foldername,user_prompt.replace(' ','').replace('.',''),rounds,ii) for ii in range(args.num_prompt)], image_history, prompt_history, reflection_history, args)
            else:
                reflection_text = ''
            reflection_history.append(reflection_text)
            trace_string = ''
            trace_string += '===========\nEnd of round %d:\n'%rounds
            trace_string += 'user_prompt: %s\n'%user_prompt
            trace_string += 'image_history: %s\n'%image_history[-1]
            trace_string += 'select_history: %s\n'%select_history[-1]
            trace_string += 'prompt_history: %s\n'%prompt_history[-1]
            trace_string += 'reflection_history: %s\n===========\n'%reflection_history[-1]
            print(trace_string)
            with open(text_record, 'a') as f:
                f.write(trace_string)
            if rounds == 0:
                os.system('cp %s output/%s/round1/%s.png'%(image_history[-1],args.foldername,user_prompt.replace(' ','').replace('.','')))
        ## save indexed image
        os.system('cp %s output/%s/iter/%s.png'%(image_history[-1],args.foldername,user_prompt.replace(' ','').replace('.','')))

        start_ind = 1
        global_best, select_response = gptv_reflection_prompt_selectbest(user_prompt, img_prompt, idea_transcript, image_history[start_ind:], args)
        global_best += start_ind
        os.system('cp %s output/%s/iter_best/%s.png'%(image_history[global_best],args.foldername,user_prompt.replace(' ','').replace('.','')))
        with open(text_record, 'a') as f:
            f.write('Final selection: %d. || '%global_best+select_response)
            f.write('===========\nFinal Selection: Round: %d.\n==========='%global_best)
    for key in ['round1','iter','iter_best']:
        os.system('cp -r output/%s/%s output/%s/tmp/%s'%(args.foldername,key,args.foldername,key))

if __name__ == '__main__':
    main()
