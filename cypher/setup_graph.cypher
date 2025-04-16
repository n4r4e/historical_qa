// Create a unique constraint on entity_id
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;

// Create a unique constraint on relation_id
CREATE CONSTRAINT relation_id_unique IF NOT EXISTS
FOR ()-[r:RELATION]-() REQUIRE r.relation_id IS UNIQUE;

// Create indexes for query performance
CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type);
CREATE INDEX entity_text_index IF NOT EXISTS FOR (e:Entity) ON (e.text);

// Load entity nodes
LOAD CSV WITH HEADERS FROM 'https://your_file_hosting_link_here.com/entities.csv' AS row
CREATE (e:Entity {
  entity_id: row.entity_id,
  type: row.type,
  text: row.text,
  normalized: row.normalized,
  confidence: toFloat(row.confidence),
  sources: row.sources
})
WITH e
// Dynamically add labels based on entity type
CALL apoc.create.addLabels(e, [e.type]) YIELD node
RETURN count(node);

// Load geospatial attributes and attach to LOCATION entities
LOAD CSV WITH HEADERS FROM 'https://your_file_hosting_link_here.com/locations.csv' AS row
MATCH (l:Entity:LOCATION {entity_id: row.entity_id})
SET l.latitude = CASE WHEN row.latitude <> '' THEN toFloat(row.latitude) ELSE null END,
    l.longitude = CASE WHEN row.longitude <> '' THEN toFloat(row.longitude) ELSE null END,
    l.display_name = row.display_name,
    l.location_type = row.location_type,
    l.importance = CASE WHEN row.importance <> '' THEN toFloat(row.importance) ELSE null END,
    l.bbox_south = CASE WHEN row.bbox_south <> '' THEN toFloat(row.bbox_south) ELSE null END,
    l.bbox_north = CASE WHEN row.bbox_north <> '' THEN toFloat(row.bbox_north) ELSE null END,
    l.bbox_west = CASE WHEN row.bbox_west <> '' THEN toFloat(row.bbox_west) ELSE null END,
    l.bbox_east = CASE WHEN row.bbox_east <> '' THEN toFloat(row.bbox_east) ELSE null END
RETURN count(l);

// Load temporal attributes and attach to TIME entities
LOAD CSV WITH HEADERS FROM 'https://your_file_hosting_link_here.com/timeperiods.csv' AS row
MATCH (t:Entity:TIME {entity_id: row.entity_id})
SET t.precision = row.precision,
    t.time_type = row.type,
    t.start_date = date(row.start_date),
    t.end_date = date(row.end_date),
    t.date_reliability = toFloat(row.date_reliability)
RETURN count(t);

// Load relations and create assertion-based graph structure
LOAD CSV WITH HEADERS FROM 'https://your_file_hosting_link_here.com/relations.csv' AS row
MATCH (subject:Entity {entity_id: row.subject_id})
MATCH (object:Entity {entity_id: row.object_id})
OPTIONAL MATCH (contextTime:Entity:TIME {entity_id: row.context_time_id})
OPTIONAL MATCH (contextLocation:Entity:LOCATION {entity_id: row.context_location_id})

// Create assertion node (intermediate node for relations)
CREATE (assertion:Assertion {
  assertion_id: row.relation_id,
  predicate: row.predicate,
  confidence: toFloat(row.confidence),
  sources: row.sources
})

// Connect subject and object via assertion node
CREATE (subject)-[:SUBJECT_OF]->(assertion)
CREATE (assertion)-[:OBJECT_IS]->(object)

// Connect temporal context if exists
FOREACH (dummy IN CASE WHEN contextTime IS NOT NULL THEN [1] ELSE [] END |
  CREATE (assertion)-[:HAS_TEMPORAL_CONTEXT]->(contextTime))

// Connect spatial context if exists
FOREACH (dummy IN CASE WHEN contextLocation IS NOT NULL THEN [1] ELSE [] END |
  CREATE (assertion)-[:HAS_SPATIAL_CONTEXT]->(contextLocation))

RETURN count(assertion);