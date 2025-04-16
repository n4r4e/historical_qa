from typing import Dict, List, Optional, Any

# LangChain 0.3.23 imports
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain_neo4j import Neo4jGraph
from langchain.chains.structured_output import create_structured_output_runnable
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema import StrOutputParser
from pydantic import BaseModel, Field

from app.config import Settings

class HistoricalKnowledgeGraphQA:
    def __init__(self):
        """Initialize the knowledge graph QA system using Neo4j and OpenAI"""
        # Load settings
        settings = Settings()
        
        # Create Neo4j graph object
        self.graph = Neo4jGraph(
            url=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password
        )
        
        # Get graph schema information
        self.graph_schema = self.get_graph_schema()
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0,
            api_key=settings.openai_api_key
        )
        
        # Initialize query transformation chain
        self.setup_query_chain()
        
        # Initialize response generation chain
        self.setup_response_chain()
    
    def get_graph_schema(self) -> str:
        """Retrieve and format the schema information from the Neo4j graph"""
        try:
            # Get node labels and property information
            node_properties = self.graph.query("""
            CALL apoc.meta.nodeTypeProperties()
            YIELD nodeType, propertyName, propertyTypes
            RETURN nodeType, collect({property: propertyName, types: propertyTypes}) as properties
            """)
            
            # Get relationship types and property information
            rel_properties = self.graph.query("""
            CALL apoc.meta.relTypeProperties()
            YIELD relType, propertyName, propertyTypes
            RETURN relType, collect({property: propertyName, types: propertyTypes}) as properties
            """)
            
            # Get entity type statistics
            entity_stats = self.graph.query("""
            MATCH (e:Entity)
            RETURN e.type AS entityType, count(*) AS count
            ORDER BY count DESC
            """)
            
            # Construct schema string
            schema = "# Knowledge Graph Schema Information\n\n"
            
            schema += "## Entity Type Statistics\n"
            for stat in entity_stats:
                schema += f"- {stat['entityType']}: {stat['count']} entities\n"
            schema += "\n"
            
            schema += "## Node Types and Properties\n"
            for node in node_properties:
                schema += f"### {node['nodeType']}\n"
                for prop in node['properties']:
                    # Handle the 'types' field safely
                    types_str = ""
                    if isinstance(prop['types'], list):
                        types_str = ', '.join(prop['types'])
                    elif isinstance(prop['types'], str):
                        types_str = prop['types']
                    else:
                        types_str = str(prop['types'])
                    
                    schema += f"- {prop['property']}: {types_str}\n"
                schema += "\n"
            
            schema += "## Relationship Types and Properties\n"
            for rel in rel_properties:
                schema += f"### {rel['relType']}\n"
                for prop in rel['properties']:
                    # Handle the 'types' field safely
                    types_str = ""
                    if isinstance(prop['types'], list):
                        types_str = ', '.join(prop['types'])
                    elif isinstance(prop['types'], str):
                        types_str = prop['types']
                    else:
                        types_str = str(prop['types'])
                    
                    schema += f"- {prop['property']}: {types_str}\n"
                schema += "\n"
            
        except Exception as e:
            print(f"Error generating schema: {e}")
            # Return a simplified schema if we can't get the full details
            schema = "# Knowledge Graph Schema Information\n\n"
            schema += "Note: Could not retrieve detailed schema information.\n\n"
        
        # Add knowledge graph structure explanation
        schema += """
## Knowledge Graph Structure Explanation
This knowledge graph contains historical events from World War I, particularly focused on events in April 1915.

1. Main Entity Types:
   - LOCATION: Places (cities, countries, regions)
   - PERSON: Individuals or groups (troops, soldiers)
   - EVENT: Historical events (battles, capitulations, bombings)
   - ORGANIZATION: Organizations (governments, military administrations)
   - TIME: Temporal information (specific dates)
   - SENTIMENT: Emotions or reactions (shock, anxiety)
   - CONCEPT: Concepts or abstract ideas

2. Assertion Nodes:
   - Intermediate nodes representing relationships between entities
   - Have 'predicate' property describing the relationship type (captured, caused, occupied)
   - Include confidence and source information

3. Key Relationships:
   - SUBJECT_OF: Connects subject entity to an Assertion
   - OBJECT_IS: Connects Assertion to object entity
   - HAS_TEMPORAL_CONTEXT: Connects Assertion to time context (when it occurred)
   - HAS_SPATIAL_CONTEXT: Connects Assertion to location context (where it occurred)

Sample Data:
- Main actors: French troops, German troops
- Key locations: Vienna, Somme, Drie-Grachten
- Key events: capitulation of Przemysl, bombing raids
- Temporal information: April 4, 1915, April 5, 1915

Query Examples:
1. Find events that occurred on a specific date:
   ```
   MATCH (subject)-[:SUBJECT_OF]->(assertion:Assertion)-[:OBJECT_IS]->(object)
   MATCH (assertion)-[:HAS_TEMPORAL_CONTEXT]->(time:Entity:TIME)
   WHERE time.start_date = date("1915-04-04")
   RETURN subject.text, assertion.predicate, object.text, time.text
   ```

2. Find events that occurred at a specific location:
   ```
   MATCH (subject)-[:SUBJECT_OF]->(assertion:Assertion)-[:OBJECT_IS]->(object)
   MATCH (assertion)-[:HAS_SPATIAL_CONTEXT]->(location:Entity:LOCATION {text: "Vienna"})
   RETURN subject.text, assertion.predicate, object.text, location.text
   ```

3. Find actions taken by a specific subject:
   ```
   MATCH (subject:Entity:PERSON {text: "French troops"})-[:SUBJECT_OF]->(assertion:Assertion)-[:OBJECT_IS]->(object)
   RETURN subject.text, assertion.predicate, object.text
   ```
"""
        
        return schema
    
    def setup_query_chain(self):
        """Set up the chain for converting natural language questions to Cypher queries"""
        # Pydantic model for Cypher query generation
        class CypherQueryOutput(BaseModel):
            query: str = Field(description="Cypher query to execute in Neo4j")
            explanation: str = Field(description="Explanation of how this query answers the natural language question")
        
        # Query generation prompt template
        query_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert system that answers natural language questions using a Neo4j knowledge graph about historical events from World War I.
You need to understand the graph schema provided below and convert natural language questions into effective Cypher queries.

{schema}

Follow these rules:
1. Generate a single, accurate Cypher query.
2. The query results should directly answer the natural language question.
3. Note: This graph only contains information about World War I events, primarily from April 1915.
4. For time-related questions, use TIME entities and HAS_TEMPORAL_CONTEXT relationships.
5. For location-related questions, use LOCATION entities and HAS_SPATIAL_CONTEXT relationships.
6. Remember that people or armies (PERSON) are often represented as groups like "French troops" or "German troops".
7. All subject-predicate-object relationships are connected through intermediate Assertion nodes, not direct edges.
8. Use SUBJECT_OF and OBJECT_IS relationships to express subject-object relationships.
9. Use toLower() function for case-insensitive string comparisons.
10. Use LIMIT to restrict the number of results (e.g., LIMIT 10).

Now generate the optimal Cypher query for the natural language question and explain it."""),
            ("human", "Question: {question}")
        ])
        
        # Use the with_structured_output method
        structured_llm = self.llm.with_structured_output(CypherQueryOutput)
        
        # Create a simple chain that combines the prompt with the structured output model
        self.query_chain = RunnablePassthrough.assign(
            query_output=lambda x: structured_llm.invoke(query_prompt.format(schema=x["schema"], question=x["question"]))
        )
    
    def setup_response_chain(self):
        """Set up the chain for generating the final response using query results"""
        response_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a knowledge graph-based question answering system for World War I history.
You need to answer natural language questions based on the provided query results.

Follow these rules when crafting your response:
1. This knowledge graph contains historical events from World War I, primarily from April 1915.
2. Provide accurate and complete answers based on the query results, considering historical context.
3. Include relevant entity, time, and location information when available to enrich your answer.
4. When explaining historical events, clearly articulate temporal sequence and causal relationships.
5. If no results are found, politely explain that the information may not be included in the current knowledge graph.
6. Present historical facts objectively and neutrally.

ALWAYS FORMAT YOUR RESPONSE USING HTML TAGS:
- Use <p> tags for paragraphs
- Use <strong> tags to emphasize important entities, names, places, dates, and key concepts
- For lists, use <ol> for numbered lists and <li> for list items
- For bullet points, use <ul> and <li> tags
- DO NOT use Markdown formatting like ** for bold; use proper HTML tags only
- Ensure proper spacing and organization of content

Analyze the structure and content of the query results thoroughly, and provide a natural, expert-like response considering the context of the user's question."""),
            ("human", """Question: {question}

Below are the query and results from the knowledge graph:

Query:
{query}

Query explanation:
{explanation}

Results:
{results}

Please provide an answer to the question based on this information.""")
        ])
        
        # Set up response generation chain
        self.response_chain = response_prompt | self.llm | StrOutputParser()
    
    def format_results(self, results: List[Dict[str, Any]]) -> str:
        """Format query results into a readable format"""
        if not results:
            return "No results found."
        
        formatted = ""
        for i, result in enumerate(results, 1):
            formatted += f"Result {i}:\n"
            for key, value in result.items():
                if isinstance(value, (dict, list)):
                    formatted += f"  {key}: {str(value)}\n"
                else:
                    formatted += f"  {key}: {value}\n"
            formatted += "\n"
        
        return formatted
    
    def process_query(self, question: str) -> str:
        """Process a natural language question and generate a response"""
        try:
            # 1. Convert natural language question to Cypher query
            query_result = self.query_chain.invoke({
                "schema": self.graph_schema,
                "question": question
            })
            
            # Access structured output
            query_output = query_result["query_output"]
            cypher_query = query_output.query
            query_explanation = query_output.explanation
            
            # 2. Execute Cypher query
            results = self.graph.query(cypher_query)
            formatted_results = self.format_results(results)
            
            # 3. Generate final response based on results
            final_response = self.response_chain.invoke({
                "question": question,
                "query": cypher_query,
                "explanation": query_explanation,
                "results": formatted_results
            })
            
            # No text processing needed as LLM will return HTML directly
            return final_response
            
        except Exception as e:
            return f"An error occurred while processing your question: {str(e)}"