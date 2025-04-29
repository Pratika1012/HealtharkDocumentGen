from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import openai
import json
import pytesseract
import logging
import pandas as pd
import time
from io import StringIO
import numpy as np
from Features.text import  extract_pdf_text, extract_text_from_word, process_text_with_GPT, image_based_warning, extract_images_and_figures_page_number,process_warning_text_with_GPT,image_discription_text,process_text_with_GPT_cer_1,process_device_discription_with_GPT_cer,key_stucture
from Features.table import pdf_to_docx_cer, extract_selected_tables_to_sheets_cer,derived_table_cer_1,final_table
from Features.image import extract_images_with_fallback,image_selection_1, final_image_output_GPT_cer,final_image_output_GPT

from doc_generate import save_text_in_document_1

pytesseract.pytesseract.tesseract_cmd = r'Tesseract-OCR\tesseract.exe'
input_tokens=0,

# Load the config file
with open('Config/configuration.json', 'r') as f:
    config = json.load(f)

openai.api_key = r"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"
# config['api_key']

logging.basicConfig(
    filename='logs/app.log',
    filemode='a',  # Append mode
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


main_prompt = """You are a Triaging Agent. Your role is to evaluate the user's query key  and **route it to the relevant only and only one agent do not route more then 1 agent** . 
  if key is text related then Text Extraction Agent call,
  if key is Image related then Image Extraction Agent,
  if key is Table related then Table Extraction Agent
- Text Extraction Agent: Summary generate, Normal text generate, Extract warning and precaution(Caution). (if do not mention any table or iamge related by default call text agent) 
- Table Extraction Agent: Derived table and Normal table
- Image Extraction Agent: Extract images

Use the send_query_to_agents tool to forward the **user's query to the relevant only any only one agents**."""

text_prompt = """You are a Text Extraction Agent. Your role is to evaluate the user's query key and route the only one tool for Sumamry generate, Normal text generate, Extract warning or precaution using the following tools:

  if key is normal text related then Normal_text_generate tool call,
  if key is summary related then Summary_generate tool call,
  if key is warning precaution related then Extract_warning_and_precaution tool call

- Summary_generate:
- Normal_text_generate if do not mention about summary or warning precaution then consider as Normal_text_generate
- Extract_warning_and_precaution :

Note: **route it to the relevant only and only one tool please do not route more then 1 tool at time** 
"""


Table_prompt = """You are a Table Extraction Agent. Your role is to by default Extract_table function call for extract table from the text:
- Extract_table
"""

Iamge_prompt = """You are an Image Extraction Agent. Your role is to  Extract Image by default using the following tool:
- Image_Extraction
"""

triage_tools = [
    {
        "type": "function",
        "function": {
            "name": "send_query_to_agents",
            "description": "Sends the user query to relevant only and only one agent based on their capabilities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agents": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "An array of agent names to send the query to."
                    },
                    "query": {
                        "type": "string",
                        "description": "The user query to send."
                    }
                },
                "required": ["agents", "query"]
            }
        },
        "strict": True
    }
]


Text_Extraction_tools = [
    {
        "type": "function",
        "function": {
            "name": "Summary_generate",
            "description": "Generate the sumarry for the given section of the text ",
           
        },
        "strict": True
    },
    {
        "type": "function",
        "function": {
            "name": "Normal_text_generate",
            "description": "if summary and warning precaution do not mention in user query then consider as Normal text.extract the text for the given section of the text",
            
        },
        "strict": True

    },
    {
        "type": "function",
        "function": {
            "name": "Extract_warning_and_precaution",
            "description": "if warning and precausion  related text mention in text then call Extract_warning_and_precaution. Extract the warning and precaution fron text",
           
        },
        "strict": True
    }
]

Table_Extraction_tools = [
    {
        "type": "function",
        "function": {
            "name": "Extract_table",
            "description": "by default Extract_table function call extract table from the text ",
           
        },
        "strict": True
    },
]

Image_Extraction_tools = [
    {
        "type": "function",
        "function": {
            "name": "Image_Extraction",
            "description": "extract Image from the text ",
           
        },
        "strict": True
    },
]



def handle_text_agent(key, value, doc, extract_text, indication, pdf_bytes):
    input_tokens = 0
    output_tokens =0
    total_tokens = 0
    
    start_time = time.time()
    flag = 0
    user_query = "Key=" + key + ":" + value
    messages = [{"role": "system", "content": text_prompt}]
    messages.append({"role": "user", "content": user_query})

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.0,
        tools=Text_Extraction_tools  # specify the function call
    )
    response_time = time.time() - start_time
    
    if response and response['choices']:
        input_tokens += response['usage']['prompt_tokens']
        output_tokens += response['usage']['completion_tokens']
        total_tokens += response['usage']['total_tokens']

        # Log the token usage and response time
        logging.info("Handle_text_agent.................")
        logging.info(f"Input Tokens: {input_tokens}")
        logging.info(f"Output Tokens: {output_tokens}")
        logging.info(f"Total Tokens: {total_tokens}")
        logging.info(f"Response generation time: {response_time:.2f} seconds")
    
    for tool_call in response.choices[0].message.tool_calls:
        print(tool_call.function.name)
        if tool_call.function.name == "Normal_text_generate":
            print(value)
            generated_response_text, token_info = process_text_with_GPT_cer_1(extract_text, value, indication)

            input_tokens += token_info.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
            output_tokens += token_info.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
            total_tokens += token_info.get('total_tokens', 0)


            print(generated_response_text)
            save_text_in_document_1(generated_response_text, doc, flag)
             
        elif tool_call.function.name == "Extract_warning_and_precaution":
            print(value)
            folder_name = "annotated_images"
            legend_image_saved = extract_images_and_figures_page_number(pdf_bytes, folder_name)
            image_warning_text, image_token_info = image_based_warning(folder_name)
            
            input_tokens += image_token_info.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
            output_tokens += image_token_info.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
            total_tokens += image_token_info.get('total_tokens', 0)


            warning_text_with_GPT, token = process_warning_text_with_GPT(image_warning_text, value)
            
            input_tokens += token.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
            output_tokens += token.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
            total_tokens += token.get('total_tokens', 0)


            save_text_in_document_1(warning_text_with_GPT, doc, flag)
                   
        else:
            pass

    # Return the token counts along with any other necessary data
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens
       }
          

def handle_table_agent(query, doc, extract_text):
    flag = 2
    table, token_usage = derived_table_cer_1(extract_text, query)  # Unpack the tuple
    if isinstance(table, tuple) and len(table) == 1:
        table = table[0]  # Extract the dictionary from the nested tuple
  
    
    if isinstance(table, dict):  # Check if table is a dictionary
        save_text_in_document_1(table, doc, flag, query)
    else:
        print("Table is not a dictionary. Please check the output of `derived_table_cer_1()`.")
    return token_usage


def handle_image_agent(query, doc, extract_text,pdf_bytes):
    flag=1
   
    # pdf_path=r"C:\Users\HP\Desktop\Dynamic_template\Input File 1.pdf"
    image_save = extract_images_with_fallback(pdf_bytes,"ExtractedImages2","ULT Chest Freezer",flag)


    image_selection,image_token=image_selection_1("ExtractedImages2","Refrigeration System")

    save_text_in_document_1(image_selection,doc,flag,query)
    return image_token




def text_extraction_json(text):
        start_time = time.time()
        response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that outputs only JSON. **Do not include any additional text or comments outside of the JSON**."
                    },
                    {   
                        "role": "user",
                        "content": f"""
                        
                    Your task is to process the content of a document divided into three main categories: summary, normal_text, and warning_precaution.
                    
                        -summary :if any section mention about summary then make key summary
                        -warning_precaution: if any section mention warning and caution or precaustion then make key warning_precaution
                        -normal_text:if above 2 key is not mention then mention normal text
                     
                        
                    **-Kindly ensure nothing is omitted from the DOC_Text.**
                    -If any category appears multiple times in the input document, append a unique identifier (e.g., 1, 2, 3, etc.) to differentiate them. Use the main categories as keys .

                    -Avoid creating sub-keys while processing.For instance, if a text part is labeled normal_text-1: "as it's written under the text part in the document", retain the structure of the input DOC Text
                    
                
                    Here is the document content:

                    DOC_Text: {text}
                        """
                        
                    }
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
        response_time = time.time() - start_time
        if response and response['choices']:
            input_tokens = response['usage']['prompt_tokens']
            output_tokens = response['usage']['completion_tokens']
            total_tokens = response['usage']['total_tokens']

        # Log the token usage and response time
        logging.info("Text Exctraction_JSON.................")
        logging.info(f"Input Tokens: {input_tokens}")
        logging.info(f"Output Tokens: {output_tokens}")
        logging.info(f"Total Tokens: {total_tokens}")
        # logging.info(f"Response generation time: {response_time:.2f} seconds")
    



            
            # Parse the JSON response from the LLM
        response_text = response['choices'][0]['message']['content'].strip()
        response_text1=json.loads(response_text)
        merged_data=key_stucture(response_text1)

        return merged_data,{"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens, "response_time": response_time}


def handle_user_message(key, value, doc, extract_text, indication, pdf_bytes):
    start_time = time.time()
    user_query = "Key=" + key + ":" + str(value)
    
    user_message = {}
    conversation_messages = []
    user_message = {"role": "user", "content": user_query}
    conversation_messages.append(user_message)

    messages = []
    messages = [{"role": "system", "content": main_prompt}]
    messages.extend(conversation_messages)

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.0,
        tools=triage_tools  # specify the function call
    )
    response_time = time.time() - start_time

    input_tokens = 0
    output_tokens =0
    total_tokens = 0

    if response and response['choices']:
        input_tokens += response['usage']['prompt_tokens']
        output_tokens += response['usage']['completion_tokens']
        total_tokens += response['usage']['total_tokens']

        # Log the token usage and response time
        logging.info("Handle_user_message.................")
        logging.info(f"Input Tokens: {input_tokens}")
        logging.info(f"Output Tokens: {output_tokens}")
        logging.info(f"Total Tokens: {total_tokens}")
        # logging.info(f"Response generation time: {response_time:.2f} seconds")
    
    # Process the response
    for tool_call in response.choices[0].message.tool_calls:
        if tool_call.function.name == 'send_query_to_agents':
            agents = json.loads(tool_call.function.arguments)['agents']
            query = json.loads(tool_call.function.arguments)['query']
            
            for agent in agents:
                print("###########################################")
                print(agent + "------------")
                
                if agent == "Text Extraction Agent":
                    # pass
                    text, token_info = text_extraction_json(value)
                    input_tokens += token_info.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
                    output_tokens += token_info.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
                    total_tokens += token_info.get('total_tokens', 0)


                    print(text.keys())
                    for key, value1 in text.items():
                        text_agent_token=handle_text_agent(key, value1, doc, extract_text, indication, pdf_bytes)
                        
                        input_tokens += text_agent_token.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
                        output_tokens += text_agent_token.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
                        total_tokens += text_agent_token.get('total_tokens', 0)




                elif agent == "Table Extraction Agent":
                    # pass
                    table_agent_token=handle_table_agent(str(value), doc, extract_text)
                    input_tokens += table_agent_token.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
                    output_tokens += table_agent_token.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
                    total_tokens += table_agent_token.get('total_tokens', 0)


                elif agent == "Image Extraction Agent":
                    # pass
                    image_agent_token=handle_image_agent(value, doc, extract_text, pdf_bytes)
                    try:
                        input_tokens += image_agent_token.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
                        output_tokens += image_agent_token.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
                        total_tokens += image_agent_token.get('total_tokens', 0)
                    except:
                        pass


    # Return the token counts along with any other necessary data
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "response_time": response_time
    }
