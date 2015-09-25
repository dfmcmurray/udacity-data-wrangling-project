
# coding: utf-8

# In[ ]:

"""
These are the solutions to the lesson 6 problem set from the "Data Wrangling with MongoDB" Udacity course.
These solutions were modified for my final project, so I've copied them here for the graders' reference.
"""


# In[1]:

### count_tags from Iterative Parsing
def count_tags(filename):
    tagCounts = {}
    for event, element in ET.iterparse(filename):
        tagCounts[element.tag] = tagCounts.get(element.tag, 0) + 1
    return tagCounts


# In[2]:

### key_type from Tag Types
def key_type(element, keys):
    if element.tag == "tag":
        if lower.search(element.get("k")):
            keys["lower"] += 1
        elif lower_colon.search(element.get("k")):
            keys["lower_colon"] += 1
        elif problemchars.search(element.get("k")):
            keys["problemchars"] += 1
        else:
            keys["other"] += 1
        
    return keys


# In[3]:

### process_map from Exploring Users
def process_map(filename):
    users = set()
    for _, element in ET.iterparse(filename):
        if element.tag == "node" or element.tag == "way" or element.tag == "relation":
            users.add(element.get("user"))

    return users


# In[5]:

### update_name from Improving Street Names
def update_name(name, mapping):

    name = " ".join(name.split(" ")[:-1] + [mapping.get(name.split(" ")[-1], name.split(" ")[-1])])

    return name


# In[6]:

### shape_element from Preparing for Database
def shape_element(element):
    node = {}
    if element.tag == "node" or element.tag == "way" :
        print element.get("lat"), element.get("lon")
        node = {
            "id" : element.get("id"),
            "type" : element.tag,
            "visible" : element.get("visible"),
            "created" : {
                "version" : element.get("version"),
                "changeset" : element.get("changeset"),
                "timestamp" : element.get("timestamp"),
                "user" : element.get("user"),
                "uid" : element.get("uid")
            }
        }
        
        address = {}
        for tagEl in element.iter("tag"):
            if problemchars.match(tagEl.get("k")):
                continue
            elif tagEl.get("k").startswith("addr:"):
                components = tagEl.get("k").split(":")
                if len(components) == 2:
                    address[components[1]] = tagEl.get("v")
            else:
                node[tagEl.get("k")] = tagEl.get("v")
        
        node_refs = []
        for ndEl in element.iter("nd"):
            node_refs.append(ndEl.get("ref"))
            
        if len(address.keys()) > 0:
            node["address"] = address
            
        if len(node_refs) > 0:
            node["node_refs"] = node_refs
            
        if element.get("lat") is not None and element.get("lon") is not None:
            node["pos"] = [ float(element.get("lat")), float(element.get("lon")) ]
                
        return node
    else:
        return None


# In[ ]:



