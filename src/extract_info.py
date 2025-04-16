# extract_info.py
import json
import re
import os
import time
from typing import List, Dict, Any, Tuple
import pandas as pd
from tqdm import tqdm
import requests
import time
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# Set the root directory for relative paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Set OpenAI API key (set as environment variable or input directly)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Preprocessing function: Split text into chunks
def split_into_chunks(text: str, max_words: int = 500) -> List[str]:
    """
    Split text into chunks with maximum max_words.
    Find sentence endings to ensure chunks end at complete sentences.
    """
    words = text.split()
    chunks = []
    current_chunk = []
    current_word_count = 0
    
    for word in words:
        current_chunk.append(word)
        current_word_count += 1
        
        if current_word_count >= max_words:
            # Find the last sentence ending in the current chunk
            chunk_text = ' '.join(current_chunk)
            last_sentence_end = max(chunk_text.rfind('. '), chunk_text.rfind('! '), chunk_text.rfind('? '))
            
            if last_sentence_end != -1:
                # Cut at the sentence end
                first_part = chunk_text[:last_sentence_end+1]
                second_part = chunk_text[last_sentence_end+2:]
                
                chunks.append(first_part)
                current_chunk = second_part.split()
                current_word_count = len(current_chunk)
            else:
                # If no period found, use the current chunk as is
                chunks.append(chunk_text)
                current_chunk = []
                current_word_count = 0
    
    # Process remaining words
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

# Article summarization function
def summarize_article(article_text: str, article_title: str, article_date: str, model: str = "gpt-4o-mini") -> str:
    """
    Use LLM to summarize an article.
    """    
    prompt = f"""    
    You are an expert in summarizing historical documents.
    The following is a newspaper article published on {article_date}. Please summarize this article concisely while preserving important entities such as people, places, time and events mentioned in the article, as well as their relationships.
    Maintain temporal and spatial information as much as possible.

    Title: {article_title}
    
    Content:
    {article_text}
    """
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )
        summary = response.choices[0].message.content
        return summary
    except Exception as e:
        print(f"Error during summarization: {e}")
        return ""

# Entity and relation extraction function (chunk-based)
def extract_entities_relations_from_chunk(chunk: str, article_title: str, article_date: str, model: str = "gpt-4o-mini") -> Dict:
    """
    Use LLM to extract entities and relations from a text chunk.
    """
    prompt = f"""
    You are an expert in extracting entities and relations from historical documents.
    The following is a portion of a newspaper article published on {article_date}.
    
    First, carefully read and understand the content. Then extract all significant entities and their relationships.
    Think step-by-step about how entities relate to each other, ensuring relationships accurately capture the meaning of the text and are logically sound.
    
    Entity types to extract include:
    - PERSON (individuals, historical figures, groups of people)
    - ORGANIZATION (governments, companies, institutions, political parties)
    - LOCATION (cities, countries, regions, landmarks, geographical features)
    - EVENT (wars, meetings, ceremonies, incidents, disasters)
    - CONCEPT (ideas, movements, policies, theories, social phenomena)
    - TIME (dates, periods, durations, eras, deadlines)
    - ARTIFACT (objects, products, technologies, buildings, monuments)
    - SENTIMENT (public opinion, social mood, emotional responses)
    
    Title: {article_title}
    
    Content:
    {chunk}
    
    Please respond in the following JSON format:
    ```json
    {{
      "entities": [
        {{"id": "E1", "type": "PERSON", "text": "person name", "confidence": 0.9}},
        {{"id": "E2", "type": "ORGANIZATION", "text": "organization name", "confidence": 0.85}},
        {{"id": "E3", "type": "LOCATION", "text": "place name", "normalized": "standardized place name", "confidence": 0.95}},
        {{"id": "E4", "type": "TIME", "text": "date or time expression", "normalized": "YYYY-MM-DD or period", "confidence": 0.8}}
      ],
      "relations": [
        {{"subject": "E1", "predicate": "relation type", "object": "E2", "context_time": "E4", "context_location": "E3", "confidence": 0.75}}
      ]
    }}
    ```
    
    Guidelines for extraction:
    1. Include "normalized" fields for both TIME and LOCATION entities with standardized forms
    2. For TIME entities, try to normalize dates to "YYYY-MM-DD" format, or "YYYY-MM" or "YYYY" if more precise information isn't available
    3. For LOCATION entities, use the most specific standardized name
    4. Only extract relationships that are explicitly or strongly implied in the text
    5. In relations, use "context_time" and "context_location" to indicate when and where the relationship took place (if mentioned)
    6. Express confidence as a value between 0.0-1.0 to represent the certainty of the information
    7. Ensure all relationships are logically coherent and match the meaning in the original text
    """
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1500
        )
        result_text = response.choices[0].message.content
        
        print(f"Result text: {result_text}") ## debugging

        # Extract just the JSON part
        json_match = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # If no JSON tags, try to find JSON format in the entire text
            json_match = re.search(r'(\{\s*"entities".*\})', result_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                return {"error": "Could not find JSON format", "raw_response": result_text}
        
        try:
            result = json.loads(json_str)
            return result
        except json.JSONDecodeError:
            return {"error": "JSON parsing error", "raw_response": result_text}
    
    except Exception as e:
        print(f"Error during entity and relation extraction: {e}")
        return {"error": str(e)}

# Entity and relation extraction function from summary
def extract_entities_relations_from_summary(summary: str, article_title: str, article_date: str, model: str = "gpt-4o-mini") -> Dict:
    """
    Use LLM to extract entities and relations from a summarized text.
    """
    prompt = f"""
    You are an expert in extracting entities and relations from historical documents.
    The following is a summary of a newspaper article published on {article_date}.
    
    First, carefully read and understand the content. Then extract all significant entities and their relationships.
    Think step-by-step about how entities relate to each other, ensuring relationships accurately capture the meaning of the text and are logically sound.
    
    Entity types to extract include:
    - PERSON (individuals, historical figures, groups of people)
    - ORGANIZATION (governments, companies, institutions, political parties)
    - LOCATION (cities, countries, regions, landmarks, geographical features)
    - EVENT (wars, meetings, ceremonies, incidents, disasters)
    - CONCEPT (ideas, movements, policies, theories, social phenomena)
    - TIME (dates, periods, durations, eras, deadlines)
    - ARTIFACT (objects, products, technologies, buildings, monuments)
    - SENTIMENT (public opinion, social mood, emotional responses)
    
    Title: {article_title}
    
    Content:
    {summary}
    
    Please respond in the following JSON format:
    ```json
    {{
      "entities": [
        {{"id": "E1", "type": "PERSON", "text": "person name", "confidence": 0.9}},
        {{"id": "E2", "type": "ORGANIZATION", "text": "organization name", "confidence": 0.85}},
        {{"id": "E3", "type": "LOCATION", "text": "place name", "normalized": "standardized place name", "confidence": 0.95}},
        {{"id": "E4", "type": "TIME", "text": "date or time expression", "normalized": "YYYY-MM-DD or period", "confidence": 0.8}}
      ],
      "relations": [
        {{"subject": "E1", "predicate": "relation type", "object": "E2", "context_time": "E4", "context_location": "E3", "confidence": 0.75}}
      ]
    }}
    ```
    
    Guidelines for extraction:
    1. Include "normalized" fields for both TIME and LOCATION entities with standardized forms
    2. For TIME entities, try to normalize dates to "YYYY-MM-DD" format, or "YYYY-MM" or "YYYY" if more precise information isn't available
    3. For LOCATION entities, use the most specific standardized name
    4. Only extract relationships that are explicitly or strongly implied in the text
    5. In relations, use "context_time" and "context_location" to indicate when and where the relationship took place (if mentioned)
    6. Express confidence as a value between 0.0-1.0 to represent the certainty of the information
    7. Ensure all relationships are logically coherent and match the meaning in the original text
    """
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1500
        )
        result_text = response.choices[0].message.content

        print(f"Result text: {result_text}") ## debugging
        
        # Extract just the JSON part
        json_match = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # If no JSON tags, try to find JSON format in the entire text
            json_match = re.search(r'(\{\s*"entities".*\})', result_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                return {"error": "Could not find JSON format", "raw_response": result_text}
        
        try:
            result = json.loads(json_str)
            return result
        except json.JSONDecodeError:
            return {"error": "JSON parsing error", "raw_response": result_text}
    
    except Exception as e:
        print(f"Error during entity and relation extraction: {e}")
        return {"error": str(e)}

# Function for deduplication and entity normalization
def merge_and_normalize_results(results: List[Dict]) -> Dict:
    """
    Merge and normalize entities and relations extracted from multiple chunks.
    Uses a unified entity ID system where all entities (including time and location)
    are treated as entities with different types.
    """
    all_entities = []
    all_relations = []
    
    # Mapping table for entity normalization
    entity_mapping = {}  # original ID -> new ID
    entity_type_text_to_id = {}  # (entity_type, normalized_text) -> new ID
    
    # Collect and normalize all entities (including location and time entities)
    entity_counter = 1
    
    for result in results:
        if "error" in result:
            continue
            
        if "entities" in result:
            for entity in result.get("entities", []):
                entity_type = entity["type"]
                normalized_text = entity["text"].strip().lower()
                
                # Create a composite key of type and text to differentiate
                # e.g., "Vienna" as a location vs "Vienna" as an organization
                type_text_key = (entity_type, normalized_text)
                
                if type_text_key in entity_type_text_to_id:
                    # If entity already exists, just update the ID mapping
                    entity_mapping[entity["id"]] = entity_type_text_to_id[type_text_key]
                else:
                    # If it's a new entity, add it and create ID mapping
                    new_id = f"E{entity_counter}"
                    entity_counter += 1
                    entity_type_text_to_id[type_text_key] = new_id
                    entity_mapping[entity["id"]] = new_id
                    
                    # Create a new entity with all properties from the original
                    new_entity = entity.copy()
                    new_entity["id"] = new_id
                    all_entities.append(new_entity)
    
    # Collect and normalize relations
    relation_signatures = set()  # To eliminate duplicate relations
    
    for result in results:
        if "relations" in result:
            for relation in result.get("relations", []):
                # Apply ID mapping for subject and object
                if relation["subject"] in entity_mapping:
                    new_subject = entity_mapping[relation["subject"]]
                else:
                    continue  # Skip if entity not mapped
                    
                if relation["object"] in entity_mapping:
                    new_object = entity_mapping[relation["object"]]
                else:
                    continue  # Skip if entity not mapped
                
                # Map context time ID
                new_context_time = None
                if "context_time" in relation and relation["context_time"] in entity_mapping:
                    new_context_time = entity_mapping[relation["context_time"]]
                    
                # Map context location ID
                new_context_location = None
                if "context_location" in relation and relation["context_location"] in entity_mapping:
                    new_context_location = entity_mapping[relation["context_location"]]
                
                # Create relation signature (for deduplication)
                signature = f"{new_subject}_{relation['predicate']}_{new_object}"
                if new_context_time:
                    signature += f"_time_{new_context_time}"
                if new_context_location:
                    signature += f"_loc_{new_context_location}"
                
                if signature not in relation_signatures:
                    relation_signatures.add(signature)
                    new_relation = {
                        "subject": new_subject,
                        "predicate": relation["predicate"],
                        "object": new_object,
                        "confidence": relation["confidence"]
                    }
                    
                    if new_context_time:
                        new_relation["context_time"] = new_context_time
                    if new_context_location:
                        new_relation["context_location"] = new_context_location
                        
                    all_relations.append(new_relation)
    
    result = {
        "entities": all_entities,
        "relations": all_relations
    }

    return result


# Main process functions

def process_chunk_based(article_data: Dict, article_date: str) -> Dict:
    """
    Method 1: Chunk-based extraction + LLM entity/relation extraction
    """
    print(f"Processing Method 1 (Chunk-based): {article_data['title']}")
    print(f"  Publication date: {article_date}")
    
    # Split into chunks
    chunks = split_into_chunks(article_data["body"])
    print(f"  Split into {len(chunks)} chunks")
    
    # Extract entities and relations from each chunk
    chunk_results = []
    for i, chunk in enumerate(tqdm(chunks, desc="Processing chunks")):
        result = extract_entities_relations_from_chunk(chunk, article_data["title"], article_date)
        chunk_results.append(result)
        # Delay to respect API rate limits
        time.sleep(1)
    
    # Merge and normalize results
    final_result = merge_and_normalize_results(chunk_results)
    return final_result

def process_summary_based(article_data: Dict, article_date: str) -> Dict:
    """
    Method 2: LLM article summarization + LLM entity/relation extraction
    """
    print(f"Processing Method 2 (Summary-based): {article_data['title']}")
    print(f"  Publication date: {article_date}")
    
    # Summarize the article
    summary = summarize_article(article_data["body"], article_data["title"], article_date)
    print(f"  Summary completed: {len(summary.split())} words")
    
    # Extract entities and relations from the summary
    result = extract_entities_relations_from_summary(summary, article_data["title"], article_date)
    return result, summary

# Main execution code
def main():
    # JSON file path
    input_file = os.path.join(ROOT_DIR, "newspapers", "NZZ_19150405.json")

    # Output directory
    output_dir = os.path.join(ROOT_DIR, "extracted_results")
    os.makedirs(output_dir, exist_ok=True)
    
    # Load data
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract metadata
    publication_date = data.get("date")

    # Select method to process (1, 2)
    methods = [1, 2]  # Change this to select the method
    
    for method in methods:
        print(f"\n=== Processing with Method {method} ===")

        # Process articles
        all_results = {}
        all_summaries = {}
        
        for i, article in enumerate(data.get("articles", [])):
            article_id = f"article_{i+1}"
            
            # Process with the selected method
            if method == 1:
                result = process_chunk_based(article, publication_date)
            elif method == 2:
                result, summary = process_summary_based(article, publication_date)
            else:
                raise ValueError(f"Invalid method selection: {method}")
            
            all_results[article_id] = result
            all_summaries[article_id] = summary if method != 1 else None
            
            # Save individual article results
            with open(f"{output_dir}/{article_id}_method{method}.json", 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        
        # Save all results
        with open(f"{output_dir}/all_results_method{method}.json", 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

        with open(f"{output_dir}/all_summaries_method{method}.json", 'w', encoding='utf-8') as f:
            json.dump(all_summaries, f, ensure_ascii=False, indent=2)
        
        print(f"Processing complete! Results saved to the {output_dir} directory.")

    print(f"\nAll methods processed! Results saved in: {output_dir}")

if __name__ == "__main__":
    main()