
# coding: utf-8

# In[3]:

### Thin out the data file for project submission ###
import xml.etree.cElementTree as ET  # Use cElementTree or lxml if too slow

OSM_FILE = "los-angeles_california.osm"  # Replace this with your osm file
SAMPLE_FILE = "los-angeles_california_thinned.osm"


def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag

    Reference:
    http://stackoverflow.com/questions/3095434/inserting-newlines-in-xml-file-generated-via-xml-etree-elementtree-in-python
    """
    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()


with open(SAMPLE_FILE, 'wb') as output:
    output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    output.write('<osm>\n  ')

    # Write every 150th top level element
    for i, element in enumerate(get_element(OSM_FILE)):
        if i % 150 == 0:
            output.write(ET.tostring(element, encoding='utf-8'))

    output.write('</osm>')


# In[ ]:



