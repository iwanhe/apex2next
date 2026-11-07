from copy import deepcopy
from apex2next_extractor import analyze_semantics
from apex2next_extractor.dependency_graph import analyze_dependency_graph

def _document():
    return {"irVersion":"1.0.0","application":{"id":"app:1","sourceFormat":"APEXLANG"},
      "objects":[
       {"id":"page:1","type":"PAGE","sourceType":"page","name":"Orders","source":{"file":"pages/p10.apx","line":1},
        "properties":{
         "source":{"valueType":"SQL_EXPRESSION","rawExpression":"SELECT * FROM orders","expressionLanguage":"SQL","classificationConfidence":"HIGH","preserved":True},
         "process":{"valueType":"PL_SQL_EXPRESSION","rawExpression":"BEGIN NULL; END;","expressionLanguage":"PL_SQL","classificationConfidence":"HIGH","preserved":True},
         "unknown":{"valueType":"UNKNOWN","rawExpression":"custom_expr(x)","expressionLanguage":"UNKNOWN","classificationConfidence":"NONE","preserved":True}}},
       {"id":"plugin:1","type":"PLUGIN","sourceType":"PLUGIN","name":"Chart Plugin","source":{},"properties":{}},
       {"id":"future:1","type":"UNKNOWN","sourceType":"FUTURE_ROUTINE","name":"Future","source":{},"properties":{}},
       {"id":"auth:1","type":"AUTHORIZATION","sourceType":"authorization","name":"Admin","source":{},"properties":{}}],
      "relationships":[],"references":[{"id":"ref:1","sourceObjectId":"page:1","referenceType":"ITEM","referenceValue":"P10_ID","resolutionStatus":"PENDING"}],
      "dependencies":[],"diagnostics":[],"metadata":{"sourceHash":"sha256:test","adapterVersion":"0.1.0"}}

def test_component_and_expression_classification_is_deterministic_and_non_mutating():
    doc=_document(); before=deepcopy(doc)
    first=analyze_semantics(doc); assert first==analyze_semantics(doc); assert doc==before
    by_id={x["objectId"]:x for x in first["objects"]}
    assert by_id["page:1"]["component"]["classification"]=="ASSISTED"
    assert by_id["future:1"]["component"]["classification"]=="UNSUPPORTED"
    assert by_id["plugin:1"]["component"]["classification"]=="MANUAL"
    expr={x["propertyPath"]:x for x in first["propertyTransformations"]}
    assert expr["source"]["target"]=="PostgreSQL query/repository"
    assert expr["process"]["classification"]=="MANUAL"
    assert expr["unknown"]["classification"]=="MANUAL"
    assert first["metadata"]["sourceExpressionsExecuted"] is False

def test_semantic_diagnostics_cover_unknown_plugin_security_and_references():
    codes={x["code"] for x in analyze_semantics(_document())["diagnostics"]}
    assert {"SEM001","SEM002","SEM003","SEM004","SEM005","SEM006"} <= codes

def test_dependency_cycle_blocks_semantic_transform_order():
    doc=_document()
    doc["dependencies"]=[
      {"id":"d1","sourceObjectId":"page:1","targetObjectId":"plugin:1","dependencyType":"USES","origin":"EXPLICIT"},
      {"id":"d2","sourceObjectId":"plugin:1","targetObjectId":"page:1","dependencyType":"USES","origin":"EXPLICIT"}]
    graph=analyze_dependency_graph(doc); result=analyze_semantics(doc,graph)
    assert any(x["code"]=="SEM007" for x in result["diagnostics"])
    assert set(graph["blockedObjectIds"])=={"page:1","plugin:1"}

def test_nested_expression_properties_are_classified_with_property_paths():
    doc=_document()
    doc["objects"][0]["properties"]["nested"]={"valueType":"OBJECT","value":{
      "handler":{"valueType":"JAVASCRIPT_EXPRESSION","rawExpression":"function () {}",
       "expressionLanguage":"JAVASCRIPT","classificationConfidence":"HIGH","preserved":True}}}
    result=analyze_semantics(doc)
    assert any(x["propertyPath"]=="nested.handler" for x in result["propertyTransformations"])
