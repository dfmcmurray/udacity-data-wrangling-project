
# coding: utf-8

# In[101]:

import xml.etree.ElementTree as ET
from sets import Set
import re
import parsedatetime
import usaddress
import urllib2
from BeautifulSoup import BeautifulSoup
from pymongo import MongoClient
import heapq


# In[3]:

### Utility Functions ###
def is_street_name(elem):
    return (elem.attrib['k'] == "addr:street")

def is_opening_hours(elem):
    return (elem.attrib['k'] == "opening_hours")


# In[47]:

### Exploring the Data: Street Names ###
count = 0
for event, elem in ET.iterparse('los-angeles_california.osm', events=("start",)):
    if elem.tag == "node" or elem.tag == "way":
        for tag in elem.iter("tag"):
            if is_street_name(tag):
                print ET.tostring(elem, 'utf-8')
                count += 1
    if count > 10:
        break
    elem.clear()


# In[45]:

#This code yields a bunch of bad data for street types
streets = Set()
for event, elem in ET.iterparse('los-angeles_california.osm', events=("start",)):
    if elem.tag == "node" or elem.tag == "way":
        for tag in elem.iter("tag"):
            if is_street_name(tag):
                streets.add(tag.get('v').split(" ")[-1])
    elem.clear()
streets


# In[58]:

#Trying a more sophisticated approach that uses natural language processing module usaddress
#https://github.com/datamade/usaddress
streets = Set()
for event, elem in ET.iterparse('los-angeles_california.osm', events=("start",)):
    if elem.tag == "node" or elem.tag == "way":
        for tag in elem.iter("tag"):
            if is_street_name(tag):
                try:
                    streets.add(str(next((st for st, comp in usaddress.parse(tag.get('v')) if comp == "StreetNamePostType"))))
                except:
                    continue
    elem.clear()
streets


# In[4]:

#The file `C1 Street Suffix Abbreviations.html` is the html downloaded from the webpage at http://pe.usps.gov/text/pub28/28apc_002.htm 
#The main table with all of the street suffix abbreviations and variations has an id of ep533076
#Its body is structured as follows, and the algorithm below uses this structure 
#to make {abbrev: full_name} pairs for each abbreviation, including the standard one if
#it's not already included in the middle column
#-------------------------------------------
#| Full Name | Abbrev #1 | Standard Abbrev |
#|  <empty>  | Abbrev #2 |     <empty>     |
#|  <empty>  | Abbrev #3 |     <empty>     |
#|  <empty>  | Abbrev #4 |     <empty>     |
#       ...        etc         ...
#-------------------------------------------
streetConversionMap = {}
soup = BeautifulSoup(open("C1 Street Suffix Abbreviations.html"))
table = soup.find('table', attrs={'id': 'ep533076'})
rows = table.findAll('tr')
numberOfRowsToSkip = 1
fullName = "thisShouldBeReassignedBeforeUseInStreetConversionMap"
for tr in rows:
    if numberOfRowsToSkip > 0:
        numberOfRowsToSkip -= 1
        continue
    cols = tr.findAll('td')
    if len(cols) == 3: #if there are three cells, then the first one is the Full Name
        fullName = str(cols[0].find(text=True)).strip()
        cols = cols[1:]
    for td in cols:
        abbreviation = str(td.find(text=True)).strip()
        if (abbreviation != '' and abbreviation != fullName):
            streetConversionMap[abbreviation] = fullName
            
streetConversionMap


# In[5]:

#Even the post office's list of abbreviations isn't complete. Scanning the LA OSM data, I found five more
#abbreviations that I could guess the full name from.
customStreetConversionMap = {
    "TR": "TRAIL",
    "BL": "BOULEVARD",
    "TL": "TRAIL",
    "TE": "TERRACE",
    "WA": "WAY"
}
streetConversionMap.update(customStreetConversionMap)
streetConversionMap


# In[58]:

### Conversion Functions ###

problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

def completeStreetTypeAbbreviation(streetName):
    streetComponents = usaddress.parse(streetName)
    reconstructedStreet = []
    for streetComponent in streetComponents:
        if streetComponent[1] != "StreetNamePostType":
            reconstructedStreet.append(streetComponent[0])
        else:
            abbreviationToConvert = re.sub("[^A-Z]+", "", streetComponent[0].upper()) #convert to upper case and remove nonalpha chars
            reconstructedStreet.append(streetConversionMap.get(abbreviationToConvert, streetComponent[0]).capitalize())
    return " ".join(reconstructedStreet)

#The heavy lifter. This function takes a raw OSM XML element and converts it to a json object matching the data model.
def shape_element(element):
    node = {}
    if element.tag == "node" or element.tag == "way":
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
        is_in = {}
        for tagEl in element.iter("tag"):
            if problemchars.match(tagEl.get("k")):          #Remove problematic attributes
                continue
            elif tagEl.get("k").startswith("addr:"):        #Structure address attribute based on data model
                components = tagEl.get("k").split(":")
                if len(components) == 2:
                    if (components[1] == "street"):
                        address[components[1]] = completeStreetTypeAbbreviation(tagEl.get("v"))
                    else:
                        address[components[1]] = tagEl.get("v")
            elif tagEl.get("k").startswith("is_in:"):        #Structure is_in attribute based on data model
                components = tagEl.get("k").split(":")
                if len(components) == 2:
                    is_in[components[1]] = tagEl.get("v")
            elif "phone" in tagEl.get("k").lower():         #Structure phone attribute based on data model
                npa, nxx, xxxx, phoneNumber = None, None, None, tagEl.get("v").strip()
                if phoneNumber.startswith("1"):
                    phoneNumber = phoneNumber[1:]
                elif phoneNumber.startswith("+1"):
                    phoneNumber = phoneNumber[2:]
                phoneNumberSections = re.findall(r'\d+', phoneNumber)
                if len(phoneNumberSections) == 3:
                    npa = phoneNumberSections[0]
                    nxx = phoneNumberSections[1]
                    xxxx = phoneNumberSections[2]
                elif len(phoneNumberSections) == 1 and len(phoneNumberSections[0]) == 10:
                    npa = phoneNumberSections[0][:3]
                    nxx = phoneNumberSections[0][3:6]
                    xxxx = phoneNumberSections[0][6:]
                if npa is not None and nxx is not None and xxxx is not None:
                    node["phone"] = {"npa": npa, "nxx": nxx, "xxxx": xxxx}
            else:
                tagKey = tagEl.get("k").replace(".", "")
                if (tagKey.startswith("$")):
                    tagKey = tagKey[1:]
                node[tagKey] = tagEl.get("v")
        
        node_refs = []
        for ndEl in element.iter("nd"):
            node_refs.append(ndEl.get("ref"))
            
        if len(address.keys()) > 0:
            node["address"] = address
            
        if len(is_in.keys()) > 0:
            node["is_in"] = is_in
            
        if len(node_refs) > 0:
            node["node_refs"] = node_refs
            
        if element.get("lat") is not None and element.get("lon") is not None:
            node["pos"] = [ float(element.get("lat")), float(element.get("lon")) ]
                
        return node
    else:
        return None


# In[8]:

### Testing the Street Name Conversion ###
count = 0
for event, elem in ET.iterparse('los-angeles_california.osm', events=("start",)):
    if elem.tag == "node":
        for tag in elem.iter("tag"):
            if is_street_name(tag):
                print shape_element(elem)
                count += 1
    if count > 10:
        break
    elem.clear()


# In[56]:

### Exploring the Data: `Way` Tags
count = 0
for event, elem in ET.iterparse('los-angeles_california.osm', events=("start",)):
    if elem.tag == "way":
        print shape_element(elem)
        count += 1
    if count > 10:
        break
    elem.clear()


# In[29]:

### SETUP MONGO DATABASE AND COLLECTION ###
client = MongoClient()
db = client.la_osm
nodes = db.nodes
ways = db.ways


# In[33]:

### INSERT DATA INTO NODES COLLECTION ###
for event, elem in ET.iterparse('los-angeles_california.osm', events=("start",)):
    if elem.tag == "node":
        nodes.insert_one(shape_element(elem))
    elem.clear()


# In[64]:

### INSERT DATA INTO WAYS COLLECTION ###
for event, elem in ET.iterparse('los-angeles_california.osm', events=("start",)):
    if elem.tag == "way":
        ways.insert_one(shape_element(elem))
    elem.clear()


# In[ ]:

### REMOVE ALL DATA FROM NODES COLLECTION ###
nodes.drop()


# In[62]:

### REMOVE ALL DATA FROM WAYS COLLECTION ###
ways.drop()


# In[181]:

### Collection Sizes ###
print nodes.count()
print ways.count()


# In[37]:

### Exploring the Data from the Mongo DB
for node in nodes.find({"address.city":{"$exists":1}}).limit(10):
    print node


# In[41]:

### Sort Cities by Count, Descending ###
for result in nodes.aggregate([{"$match":{"address.city":{"$exists":1}}}, {"$group":{"_id":"$address.city", "count":{"$sum":1}}}, {"$sort":{"count":-1}}]):
    print result


# In[44]:

### Exploring the Data: Pasadena Amenities
for result in nodes.find({"address.city":"Pasadena"}):
    print result.get("name")


# In[52]:

### Exploring the Data: Biggest Contributor to Nodes
nodes.aggregate([{"$group":{"_id":"$created.user", "count":{"$sum":1}}}, {"$sort":{"count":-1}}, {"$limit":1}]).next()


# In[67]:

### Exploring the Data: Ways with Names
for way in ways.find({"name":{"$exists":1}}).limit(10):
    print way


# In[86]:

### Exploring the Data: Way with the Most Refs
longestNodeRefsArray = ways.aggregate([{"$project": {"_id":"$_id", "node_refs":"$node_refs", "size": {"$size":{ "$ifNull": [ "$node_refs", [] ] }}}}, {"$sort":{"size":-1}}, {"$limit": 1}]).next()
ways.find_one({"_id":longestNodeRefsArray["_id"]})


# In[131]:

### Reporting Some General Descriptive Statistics ###
def uniqueUsers(collection):
    return set(collection.distinct("created.user"))

nodeCount = nodes.count()
wayCount = ways.count()
print "Total Number of Nodes:\t\t", nodeCount
print "Total Number of Ways:\t\t", wayCount
print "Total Number of All Documents:\t", nodeCount + wayCount
print 

uniqueUsersInNodes = uniqueUsers(nodes)
uniqueUsersInWays = uniqueUsers(ways)
print "Unique Users in Nodes:\t\t", len(uniqueUsersInNodes)
print "Unique Users in Ways:\t\t", len(uniqueUsersInWays)
print "Unique Users in All Documents:\t", len(uniqueUsersInNodes | uniqueUsersInWays)
print 


# In[134]:

### Top Contributor Statistics ###
def topContributingUsers(limit, *collections):
    if limit <= 0:
        return None
    contributors = {}
    for collection in collections:
        for contributor in collection.aggregate([{"$group":{"_id":"$created.user", "count":{"$sum":1}}}]):
            contributionCount = contributors.get(contributor["_id"], 0) + contributor["count"]
            contributors[contributor["_id"]] = contributionCount
    return heapq.nlargest(limit, contributors.items(), lambda pair: pair[1])

topContributorLimit = 10
topContributorsInNodes = topContributingUsers(topContributorLimit, nodes)
topContributorsInWays = topContributingUsers(topContributorLimit, ways)
topContributorsInAllDocuments = topContributingUsers(topContributorLimit, nodes, ways)
print "Top {} Contributors in Nodes:".format(topContributorLimit)
print "".join(["{:<30}{:<10}({:.2%})\n".format(username, contributionCount, float(contributionCount) / nodeCount) for username, contributionCount in topContributorsInNodes])
print "Top {} Contributors in Ways:".format(topContributorLimitPerList)
print "".join(["{:<30}{:<10}({:.2%})\n".format(username, contributionCount, float(contributionCount) / wayCount) for username, contributionCount in topContributorsInWays])
print "Top {} Contributors in All Documents:".format(topContributorLimitPerList)
print "".join(["{:<30}{:<10}({:.2%})\n".format(username, contributionCount, float(contributionCount) / (nodeCount + wayCount)) for username, contributionCount in topContributorsInAllDocuments])


# In[167]:

### Top Amenities Statistics ###
def topAmenities(limit, collection):
    return collection.aggregate([{"$match":{"amenity":{"$exists":1}}}, {"$group":{"_id":"$amenity","count":{"$sum":1}}}, {"$sort":{"count":-1}}, {"$limit":limit}])

def keyToTitle(key):
    return key.replace("_", " ").title()

topAmenitiesLimit = 10
topAmenitiesList = topAmenities(topAmenitiesLimit, nodes)
print "Top {} Amenity Types:".format(topAmenitiesLimit)
print "".join(["{:<30}{:<10}\n".format(keyToTitle(amenity["_id"]), amenity["count"]) for amenity in topAmenitiesList])


# In[169]:

### Top Restaurant Statistics ###
def topCuisines(limit, collection):
    return collection.aggregate([{"$match":{"cuisine":{"$exists":1}, "amenity":"restaurant"}}, {"$group":{"_id":"$cuisine", "count":{"$sum":1}}}, {"$sort":{"count":-1}}, {"$limit":limit}])

def topRestaurants(limit, collection):
    return collection.aggregate([{"$match":{"name":{"$exists":1}, "amenity":"restaurant"}}, {"$group":{"_id":"$name", "cuisines":{"$push":"$cuisine"}, "count":{"$sum":1}}}, {"$sort":{"count":-1}}, {"$limit":limit}])

def keyToTitle(key):
    return key.replace("_", " ").title()

topCuisinesLimit = 15
topRestaurantsLimit = 20
topCuisinesList = topCuisines(topCuisinesLimit, nodes)
topRestaurantsList = topRestaurants(topRestaurantsLimit, nodes)
print "Top {} Cuisines:".format(topCuisinesLimit)
print "".join(["{:<30}{:<10}\n".format(keyToTitle(cuisine["_id"]), cuisine["count"]) for cuisine in topCuisinesList])
print "Top {} Restaurants:".format(topRestaurantsLimit)
print "".join(["{:<30}{:<10}({})\n".format(restaurant["_id"], restaurant["count"], ", ".join(set(map(keyToTitle, restaurant["cuisines"])))) for restaurant in topRestaurantsList])


# In[179]:

### Number of In N Outs
len(list(nodes.aggregate([{"$match":{"name":"In N Out"}}])))


# In[ ]:



