import pdfplumber
import os
import pandas as pd
import openai
import json
import fitz
from datetime import datetime
import numpy as np
import logging
import tempfile
import time
from docx import Document
from io import BytesIO
import time
import logging
from datetime import datetime
import tempfile
from pdf2docx import Converter
from pdf2docx import Converter
from langchain_community.document_loaders import PyPDFLoader
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.callbacks import get_openai_callback
import tiktoken

with open('Config/configuration.json', 'r') as f:
    config = json.load(f)

openai.api_key = config['api_key']
logging.basicConfig(
    filename='logs/app.log',
    filemode='a',  # Append mode
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)



timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")


def pdf_to_docx_cer(pdf_path):
    """
    Converts a PDF file to a DOCX file and returns the path to the DOCX file.
    """
    try:
        # Convert PDF to DOCX using pdf2docx
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(pdf_path)
            temp_pdf_path = temp_pdf.name  # Get the path of the temporary file
        
        # Define output paths
        timestamp = time.time()
        docx_path = f'templates/output_{timestamp}.docx'
        
        # Convert PDF to DOCX using pdf2docx
        cv = Converter(temp_pdf_path)  # Pass the file path, not bytes
        cv.convert(docx_path, start=0, end=None)  # Convert all pages
        cv.close()
        print(f"PDF converted to DOCX and saved as {docx_path}")

        return docx_path

    except Exception as e:
        logging.error(f"Error converting PDF to DOCX: {e}")
        return None

# Extract and save tables containing specific columns to Excel
def extract_selected_tables_to_sheets_cer(doc_path, required_columns):
    excel_path = f'pdf_path_{timestamp}.xlsx'
    # Load Word document
    doc = Document(doc_path)
    
    # Initialize storage for multiple sheets
    sheets_data = []
    current_table_data = []

    # Variables to store the null counts
    Page1_LR = 0
    Page1_LR_1 = 0
    Page2_FR = 0
    Page2_FR_1 = 0

    try:
        for i, table in enumerate(doc.tables):
            # Extract rows from each table
            table_data = []
            for row in table.rows:
                row_data = [cell.text.strip() if cell.text.strip() != "" else None for cell in row.cells]
                table_data.append(row_data)

            # Check if `current_table_data` has rows (i.e., it’s not the first table)
            if current_table_data and contains_required_columns(current_table_data, required_columns):
                try:
                    # Calculate null counts for merging logic
                    Page1_LR = count_nulls(current_table_data[-1])  # Last row on Page 1
                    Page1_LR_1 = count_nulls(current_table_data[-2])  # Second last row on Page 1
                    Page2_FR = count_nulls(table_data[0])  # First row on Page 2
                    Page2_FR_1 = count_nulls(table_data[1])  # Second row on Page 2
                except IndexError as e:
                    print("IndexError during row access:", e)
                    print("Skipping merge check for this table due to insufficient rows.")
                    # Skip merging and continue with the next table
                    sheets_data.append(current_table_data)
                    current_table_data = table_data
                    continue

                # Check merging condition
                if (
                    (Page1_LR >= Page1_LR_1 and Page2_FR >= Page2_FR_1) and
                    (Page1_LR != Page1_LR_1 or Page1_LR != Page2_FR or Page1_LR != Page2_FR_1) and
                    (Page1_LR != Page2_FR or Page2_FR != Page2_FR_1)
                ):
                    # Merge the last row of `current_table_data` with the first row of `table_data`
                    merged_row = [
                        f"{str(cell1) if cell1 is not None else ''} {str(cell2) if cell2 is not None else ''}".strip()
                        for cell1, cell2 in zip(current_table_data[-1], table_data[0])
                    ]
                    
                    # Replace the last row of `current_table_data` with the merged row
                    current_table_data[-1] = merged_row

                    # Directly extend `current_table_data` with the remaining rows from `table_data` (skipping the first row)
                    current_table_data.extend(table_data[1:])
                else:
                    # If no merge, append `current_table_data` to `sheets_data` and start a new table
                    sheets_data.append(current_table_data)
                    current_table_data = table_data  # Start a new collection with the current table rows
            else:
                # If it's the first table, start collecting rows
                current_table_data = table_data

        # Save the last table data if it contains the required columns
        if current_table_data and contains_required_columns(current_table_data, required_columns):
            sheets_data.append(current_table_data)
    
    except Exception as e:
        print("An unexpected error occurred:", e)
        print("Returning partially processed data.")

    # Save data to Excel
    with pd.ExcelWriter(excel_path) as writer:
        for idx, sheet in enumerate(sheets_data):
            # Replace None values with empty strings for Excel display
            df = pd.DataFrame(sheet).replace({None: "", np.nan: ""})
            mask = df.duplicated(subset=[df.columns[0], df.columns[-1]], keep='last')
            df = df[~mask].reset_index(drop=True)
            df.columns = df.iloc[0]  # Set the first row as the header
            df = df[1:].reset_index(drop=True)
            df.to_excel(writer, sheet_name=f'Sheet_{idx + 1}', index=False)
    
    excel_data = pd.ExcelFile(excel_path)

    all_sheets_list = [excel_data.parse(sheet_name) for sheet_name in excel_data.sheet_names]

    print(f"Selected tables saved to {excel_path}")
    return all_sheets_list



# Helper function to count nulls in a row
def count_nulls(row):
    """
    Counts the number of null (None) values in a given row.
    """
    try:
        return sum(1 for cell in row if cell is None)
    except TypeError as e:
        logging.error(f"Error processing row: {e}")
        return 0

# Helper function to check if a table contains the required columns

def contains_required_columns(table_data, required_columns):
    """
    Checks if any of the required columns are in the first row (assumed to be the header).
    """
    try:
        if not table_data:
            raise ValueError("The table data is empty.")
        
        header = table_data[0]
        return any(column in header for column in required_columns)
    except IndexError as e:
        logging.error(f"Error accessing the header of the table: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error in contains_required_columns function: {e}")
        return False


# Helper function to check if tables are continuous
def is_continuous(current_table_data, previous_table_data):
    """
    Checks if the current table is continuous with the previous table based on headers.
    """
    try:
        if not previous_table_data:
            return False
        
        # Check if headers match for continuity
        if current_table_data[0] == previous_table_data[0]:
            return True
        
        return False
    except IndexError as e:
        logging.error(f"Error accessing table headers: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error in is_continuous function: {e}")
        return False

# Derived table extraction
def derived_table_cer(pdf_text,Reference_Text):


    start_time = time.time()
                
    # Use ChatCompletion to strictly return JSON
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
               Please only extract the values for **1) Device Legal Manufacturer: 2)Devices covered by the CER:** section in the Referance Text.
                - maintain json structure.like heading then table name and data as it is from Reference Text

                -If any field is missing, please fill with "User Input Required".
                
                PDF Text:
                {pdf_text}
                Reference Text:{Reference_Text}

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
        logging.info("derived_table_cer.................")
        logging.info(f"Input Tokens: {input_tokens}")
        logging.info(f"Output Tokens: {output_tokens}")
        logging.info(f"Total Tokens: {total_tokens}")
        logging.info(f"Response generation time: {response_time:.2f} seconds")

        # Parse the JSON response from the LLM
        response_text = response['choices'][0]['message']['content'].strip()
        
        try:
            json_output = json.loads(response_text)
        except json.JSONDecodeError:
            logging.error("Failed to decode JSON from LLM response. Returning an empty JSON structure.")
            json_output = {}

        # Return the JSON output and token usage
        return json_output, {'input_tokens': input_tokens, 'output_tokens': output_tokens, 'total_tokens': total_tokens}
    else:
        return None,None











def final_table(pdf_name,model_name):
    table=[]

    # loader = PyPDFLoader(BytesIO(pdf_name))
    # pages = loader.load()
    pdf_content = ""
    pdf_stream = BytesIO(pdf_name)
    with pdfplumber.open(pdf_stream) as pdf:
        for page in pdf.pages:
            # Extract text from each page
            page_text = page.extract_text()
            if page_text:  # Avoid adding NoneType
                pdf_content += page_text + "\n"
    
    # Open the PDF from bytes
    
# Combine the text content from all pages into one large string
    # pdf_content = " ".join(page.page_content for page in pages)

    model = ChatOpenAI(model="gpt-4o",api_key=config['api_key'], verbose=True)  # Enable verbose mode for token logging
    prompt_template = """
         all relevant information from the given PDF text that corresponds to the specified model number, and organize the extracted details into a structured JSON format based on the following columns:

        {{
            Columns: {desired_columns}
            Model Number: {model_number}
            
        }}

        PDF Text: {content}

       Instructions:

            For each JSON key, assign only one value. If multiple values are found, create separate JSON objects for each.

            Treat an asterisk (*) or "XXX" in a model number as a wildcard for any character or digit, and generate all possible model variations in the output.

            **If a model name has variations with [A, D, V, Y] as the last character, include only those with "V" as the final character and extract all associated information for that models.**

            If a key's value is not available, indicate "User Input Required."

            If the model number isn’t provided, analyze PDF text headings to identify model series references and use those series as a basis.

            **Replace any asterisk (*) in the model number with the corresponding matching character(s) found in the extracted information.**
        """
    prompt = PromptTemplate(template=prompt_template, input_variables=["content", "model_number", "desired_columns"])

    # Step 3: Set Up the Output Parser and Chain
    json_parser = JsonOutputParser()
    chain = prompt | model | json_parser

    # Desired columns and model number
    desired_columns = ['Model', 'Rated Voltage', 'Rated current', 'Frequency/Phase', 'Shipping Weight', 'internal Dimensions', 'External Dimensions']
    
    extracted_data = chain.invoke({"content": pdf_content, "model_number": model_name, "desired_columns": desired_columns})
    try:
        refined_df = pd.DataFrame(extracted_data)
    except:
        refined_df = pd.DataFrame([extracted_data])

    table.append(refined_df)       
                # Print the refined DataFrame in the terminal
               
    return table



################### dynamic table###################################3


# def derived_table_cer_1(pdf_text,Reference_Text):


    
                
#     start_time = time.time()
#     # Use ChatCompletion to strictly return JSON
#     response = openai.ChatCompletion.create(
#         model="gpt-4o",
#         messages=[
#             {
#                 "role": "system",
#                 "content": "Your task is to process the provided text and extract values to generate a structured JSON format. Follow the instructions and guidelines below: "
#             },
#             {   
#                 "role": "user",
#                 "content": f"""
#                 Your task is to process the provided text and extract values to generate a structured JSON format. Follow the instructions and guidelines below:

#                 Instructions:

#                 JSON Structure Requirements:
#                 Organize extracted data under separate table_x keys (e.g., table_1, table_2, etc.) if multiple tables are identified.
#                 Each table should be represented as an array of JSON objects, where each object contains key-value pairs for the corresponding columns and their extracted values.
                
#                 Data Extraction Rules:
#                 Extract values for specified columns from the provided PDF text. If a column is missing from the text, populate it with "User Input Required".
#                 For columns related to classifications or class, explicitly set their values as "User Input Required".
#                 If multiple values are found for a single column, split them into separate JSON objects.
                
#                 Example:          
#                  {{table_1:[{{
#                     "columns":values,
#                     }}], 
#                 table_2:[{{
#                     "columns":values,
#                     }}],
#                 }}
                                
#                 PDF Text:
#                 {pdf_text}
#                 Reference text:{Reference_Text}

#                 """
#             }
#         ],
#         temperature=0.0,
#         response_format={"type": "json_object"}
#     )
    

#     response_time = time.time() - start_time
#     if response and response['choices']:
#         input_tokens = response['usage']['prompt_tokens']
#         output_tokens = response['usage']['completion_tokens']
#         total_tokens = response['usage']['total_tokens']

#         # Log the token usage and response time
#         logging.info("derived_table_cer_1.................")
#         logging.info(f"Input Tokens: {input_tokens}")
#         logging.info(f"Output Tokens: {output_tokens}")
#         logging.info(f"Total Tokens: {total_tokens}")
#         logging.info(f"Response generation time: {response_time:.2f} seconds")

        
#     # Parse the JSON response from the LLM
#     response_text = response['choices'][0]['message']['content'].strip()
    
#     tables={}
#     try:
#         json_output = json.loads(response_text)
#         return json_output,{"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens, "response_time": response_time}
#     except json.JSONDecodeError:
#         print("Failed to decode JSON from LLM response. Returning an empty JSON structure.")
#         return None


def derived_table_cer_1(pdf_text,reference_text):
    model = ChatOpenAI(model="gpt-4o",api_key=config['api_key'], temperature=0.2, verbose=True)  # Enable verbose mode for token logging
    prompt_template = """
    

        {{
            PDF Text: {pdf_text}
        Reference_Text:{reference_text}
            
        }}

    
    Your task is to process the provided text and extract values to generate a structured JSON format. Follow the instructions and guidelines below:

        Instructions:

        JSON Structure Requirements:
        Organize extracted data under separate table_x keys (e.g., table_1, table_2, etc.) if multiple tables are identified.
        Each table should be represented as an array of JSON objects, where each object contains key-value pairs for the corresponding columns and their extracted values.
        
        Data Extraction Rules:
        Extract values for specified columns from the provided PDF text. If a column is missing from the text, populate it with "User Input Required".
        For columns related to classifications or class, explicitly set their values as "User Input Required".
        If multiple values are found for a single column, split them into separate JSON objects.
                        
        example:-
        {{
        "table_1": [
            {{
            "heading": "Heading for Table 1 ",
            "table_name": "Table Name",
            "columns": [{{"columns":values,}},]
            }}
        ],
        "table_2": [
            {{
            "heading": "Heading for Table 2",
            "table_name": "Table Name",
            "columns":  [{{"columns":values,}},]
            }}
        ]
        }}

        - **generate the table_name key only if a "table name" is present in the "Reference_Text". However, If the "Reference_Text" does not contain a "table name," do not generate the table_name key yourself.**
        - do not generate "columns" key more then one times for one table
        - if any heding store write or replace generic name then replace with generic name with this part                
        """
    
    encoding= tiktoken.encoding_for_model("gpt-4o")
    prompt = PromptTemplate(template=prompt_template, input_variables=["reference_text", "pdf_text"])
    input_string=prompt_template+reference_text+pdf_text
    input_tokens=len(encoding.encode(input_string))

    # Step 3: Set Up the Output Parser and Chain
    json_parser = JsonOutputParser()
    chain = prompt | model | json_parser

    # Desired columns and model number
    
    

    extracted_data = chain.invoke({"reference_text": reference_text, "pdf_text": pdf_text})
    output_tokens=len(encoding.encode(str(extracted_data)))
    total_tokens=input_tokens + output_tokens

    logging.info("derived_table_cer_1.................")
    logging.info(f"Input Tokens: {input_tokens}")
    logging.info(f"Output Tokens: {output_tokens}")
    logging.info(f"Total Tokens: {total_tokens}")

    return extracted_data,{"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens}