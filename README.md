# Custom Idea2Img

### Cloned from the Official Repo of [Idea2Img](https://idea2img.github.io/) 

### Introduction

Modifying the Idea2Img Code for custom use by adapting it to the latest models.

#### Changes so far
Added support to access and send API requests using Managed identity, modified code to support GPT-4o and restructured the request body data format such that is suitable for the AzureOpenAI GPT-4o model.

### WIP
Modifying and switching the T2I models to the latest ones - SD3 and Flux Dev

### Prerequisites

* Obtain the public [Azure OpenAI GPT-4o API key]([https://platform.openai.com/docs/guides/vision](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models?tabs=python-secure#gpt-4o-and-gpt-4-turbo)) and setup T2I inference accordingly, e.g., [SD3](https://huggingface.co/stabilityai/stable-diffusion-3-medium) and [Flux Dev](https://huggingface.co/black-forest-labs/FLUX.1-dev).

## Installation

1. Clone the repository

    ```
    git clone https://github.com/DeepthiSudharsan/custom-idea2img.git
    ```

### Running
2. Inference prompts will be read from ``--testfile``. ``<IMG>`` is a separator token inserted between image-image and image-text.

    ```
    mkdir output
    python idea2img_pipeline.py --testfile testsample.txt --fewshot --select_fewshot
    ```

### Results
3. Generated results and intermediate steps will be saved to ``output`` folder.

<p align="center">
  <img src="./main_de3.png" width="75%"/>
</p>
