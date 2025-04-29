
import os
import re
import shutil 
from Features.text import  extract_pdf_text, extract_text_from_word, process_text_with_GPT, image_based_warning, extract_images_and_figures_page_number,process_warning_text_with_GPT,image_discription_text,process_text_with_GPT_cer_1,process_device_discription_with_GPT_cer,dynamic_reference
from Features.table import pdf_to_docx_cer, extract_selected_tables_to_sheets_cer,derived_table_cer,final_table,derived_table_cer_1
from Features.image import extract_images_with_fallback,image_selection_1, final_image_output_GPT_cer,final_image_output_GPT
from Features.dynamic_template import handle_user_message,text_extraction_json
import logging
from doc_generate import save_text_in_document
from docx import Document
import json
import os
from docx import Document
import io
import time
import datetime
import streamlit as st



def extraction(flag, indication, model_number,input_file_text,output_file_text):
    if flag==0:
            token_info=[]
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0    
            for document in input_file_text:
                file_name = os.path.splitext(document.name)[0]

                pdf_bytes = document.read()
        # Text Extraction and GPT processing

                folder_name="annotated_images"

                extract_text = extract_pdf_text(pdf_bytes)

                reference_content = extract_text_from_word(output_file_text)

                legend_image_saved = extract_images_and_figures_page_number(pdf_bytes,folder_name)
                image_warning_text,image_token_info = image_based_warning(folder_name)
                print(image_warning_text)

                token_info.append(image_token_info)
                input_tokens += image_token_info.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
                output_tokens += image_token_info.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
                total_tokens += image_token_info.get('total_tokens', 0)
                
                warning_text_with_GPT,warning_token_info = process_warning_text_with_GPT(image_warning_text,reference_content)
                token_info.append(warning_token_info)
                
                input_tokens += warning_token_info.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
                output_tokens += warning_token_info.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
                total_tokens += warning_token_info.get('total_tokens', 0)
                # # Process text with GPT, assuming it returns both the result and token info
                generated_response_text, text_token_info = process_text_with_GPT(extract_text, reference_content)
                
                token_info.append(text_token_info)
                input_tokens += text_token_info.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
                output_tokens += text_token_info.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
                total_tokens += text_token_info.get('total_tokens', 0) 
        # Image Extraction
            
                name= "control panel"
                image_save =extract_images_with_fallback(pdf_bytes,"ExtractedImages2",name,flag)

                image_selection,image_token_info_1=image_selection_1("ExtractedImages2",name)
                token_info.append(image_token_info_1)
                input_tokens += image_token_info_1.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
                output_tokens += image_token_info_1.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
                total_tokens += image_token_info_1.get('total_tokens', 0)
                print("---------------------------------------")
                print(image_selection)

                if image_selection and "found" not in image_selection:
                    # Clean up the image name
                    image = image_selection.replace("-", "").strip()
                    
                    # Extract the number from the image name
                    number = int(image.split('_')[-1].split('.')[0])
                
                    # Prepare the page numbers for extraction
                    page_num = [number-2,number-1, number, number + 1,number + 2]
                    logging.info(page_num)
    
                    # Extract text from the PDF document
                    extract_image_text = image_discription_text(pdf_bytes,page_num)
                
                    # Generate the final output based on the extracted text
                    final_text,image_description_token_info = final_image_output_GPT(extract_image_text, reference_content)
                    token_info.append(image_description_token_info)

                    input_tokens += image_description_token_info.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
                    output_tokens += image_description_token_info.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
                    total_tokens += image_description_token_info.get('total_tokens', 0)

                else:
                    image = None
                 
                    final_text = "Image is not found"
                  
        # Table Extraction 
                
                user_input = model_number  
                
                pattern = r"^([A-Za-z]+)\w*(\d{2}\w?)$"
                match = re.match(pattern, user_input)
                if match:
                    pattern1 = fr"^{match.group(1)}.*{match.group(2)}(?:[Vv])?$"
                else:
                    pattern1=model_number

                extract_tables = final_table(pdf_bytes, pattern1)
                
            
                
                
                # warning_text_with_GPT=""
                # generated_response_text=""
                # final_text=""
                # image=None
                # print(extract_tables)
                
                text=save_text_in_document(generated_response_text,warning_text_with_GPT,final_text,image,extract_tables)
    
                if os.path.exists("ExtractedImages2"):
           
                    shutil.rmtree("ExtractedImages2")
       

                return text,file_name,token_info,input_tokens,output_tokens,total_tokens





###################################----CER-----########################################


    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        token_info=[]
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        model_number=''
        for document in input_file_text:
                file_name = os.path.splitext(document.name)[0]
                pdf_bytes = document.read()


               

        

                extract_text = extract_pdf_text(pdf_bytes)
                reference_content = extract_text_from_word(output_file_text)
                
                
                # st.write(reference_content)
                # dynamic_json_reference = """{'Text-1': 'Scope of the Clinical Evaluation\n 1  Introduction:\n Provide details of Identification of devices covered by the clinical evaluation report, products, models, sizes, software versions, accessories, their proprietary names, code names assigned during device development. Whether the clinical evaluation is submitted to the MDD directive. Concise physical and chemical description, including materials. Whether the device incorporated medicinal substances (already on the market or new), tissues, or blood products. Mechanical and physicochemical characteristics; others (such as sterile vs. nonsterile, radioactivity etc.); Technologies used, whether the device is based on a new technology, a new clinical application of an existing technology, or the result of incremental change of an existing technology. Description of innovative aspects of the device.\n\n\n 2  Process Used to Perform Clinical Evaluation: \nPrint the following: “This Clinical Evaluation follows the process described in Annex XIV, Part A of the MDR and summarized as:\n- Establish/update the clinical evaluation plan;\n- Identify available clinical data relevant to the device and its intended purpose and any gaps inclinical evidence through a systematic literature review;\n- Appraise all relevant clinical data by evaluating in terms of its suitability for establishing the safety and performance of the device;\n- Generate any new or additional clinical data needed to address outstanding issues, through properly designed clinical investigations in 

                # dynamic_json_reference=json.loads(dynamic_json_reference)
                dynamic_json_reference,dynamic_json_reference_token=dynamic_reference(reference_content)
               

                input_tokens += dynamic_json_reference_token.get('input_tokens', 0)  # Add 0 if 'input_tokens' is not present
                output_tokens += dynamic_json_reference_token.get('output_tokens', 0)  # Add 0 if 'output_tokens' is not present
                total_tokens += dynamic_json_reference_token.get('total_tokens', 0)
               
                # st.write(dynamic_json_reference)
                # print(dynamic_json_reference)
                print("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
                
                template_path = f"templates\\output_template.docx"


# Create a new file name
                new_file_name = "CER_Output.docx"

                # Load the template
                doc = Document(template_path)

                # Iterate over your dynamic_json_reference and handle the content
                for key, value in dynamic_json_reference.items():
                    print(value)
                    
                    response_data = handle_user_message(key, value, doc, extract_text, indication, pdf_bytes)

                    input_tokens += response_data.get('input_tokens',0)
                    output_tokens += response_data.get('output_tokens',0)
                    total_tokens += response_data.get('total_tokens',0)
                    
                # Save the document to a new file
                new_file_path = f"templates\\{new_file_name}"  # Update this path as needed
                doc.save(new_file_path)

                # Optional: if you still want to use BytesIO for in-memory processing
                output = io.BytesIO()
                doc.save(output)
                output.seek(0)

                return output,file_name,token_info,input_tokens,output_tokens,total_tokens

    


