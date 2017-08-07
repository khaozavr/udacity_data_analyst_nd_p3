
# coding: utf-8

# # P3: OpenStreetMap

# I'm using data form the north-eastern part of Berlin, Germany. It's the place I live and spend most of my time around, so it's interesting to see what the OpenStreetMap data for it looks like.
# 
# First things first, all the necessary imports.

# In[1]:

#!/usr/bin/env python


import xml.etree.cElementTree as ET
import pprint
import csv
import codecs
import re

OSMFILE = 'berlin_nordost.osm'


# I decided to audit street names and phone numbers, as these have a large probability of having been messed up. 
# 
# Having run my auditing script against a list of expected German street types and a promising initial formatting of phone number strings, this is what I got.

# In[19]:

# A list of expected German street types. Each can be capitalized if it's a separate word (e.g. Prenzlauer Allee), 
# or lowercase if it's all one word (e.g. Kastanienallee). Unicode coding for "ß" and "ü" is necessary.
expected = [u"Stra\xdfe", u"stra\xdfe", "Allee", "allee", "Weg", "weg", "Platz", "platz", "Gasse", "gasse", 
            "Promenade", "promenade", "Ufer", "ufer", u"Br\00fccke", u"br\00fccke"]

def audit_street_type(street_types, street_name):
    ''' 
    If unexpected street type, add to set.
    '''
    counter = 0
    for street_type in expected:
        if street_type in street_name:
            counter += 1
    if counter == 0:
        street_types.add(street_name)
        
def audit_phone_num(phone_nums, num):
    '''
    If badly formatted phone number, add to set.
    '''
    if not num.startswith("+49 30 "):
        phone_nums.add(num)

def is_street_name(elem):
    '''
    Check if the tag describes a street name.
    '''
    return (elem.attrib['k'] == "addr:street")

def is_phone_num(elem):
    '''
    Check if the tag describes a phone number associated with the object.
    '''
    return (elem.attrib['k'] == "phone")

def audit(osmfile):
    '''
    Run through all street names and phone numbers in data, return unexpected street types and numb.
    '''
    osm_file = open(osmfile, "r")
    street_types = set([])
    phone_nums = set([])
    for event, elem in ET.iterparse(osm_file, events=("start",)):
        if elem.tag == "node" or elem.tag == "way":
            for tag in elem.iter("tag"):
                if is_street_name(tag):
                    audit_street_type(street_types, tag.attrib['v'])
                elif is_phone_num(tag):
                    audit_phone_num(phone_nums, tag.attrib['v'])
    osm_file.close()
    return street_types, phone_nums

street_phone_list = audit(OSMFILE)

pp = pprint.PrettyPrinter(indent=4)
print "Streets:"
pp.pprint(list(street_phone_list[0])[:30])
print "\nPhone numbers:"
pp.pprint(list(street_phone_list[1])[:30])


# Ok, by and large these are legitimate street names that don't have a particular type. (Some weird codings in there are unicode for the German ü, ö, ä and ß). It's not uncommon in Germany to name the streets whatever (e.g. "Am Ostbahnhof" = "At the Eastern Station").
# 
# But, there are some problems that I notice:
# * some street types are abbreviated, e.g. "Str." instead of "Straße"
# * others have "ss" instead of "ß", which is an informal "international" variant of German orthography
# * some names are not properly capitalized
# 
# As for the phone numbers, they are just one huge mess. To be fair, the existing standard format is not very well enforced, but it's a bad excuse for having such a chaos in our data, isn't it? The standard phone number format for Berlin is: +49 30 1234567. No brackets, no hyphens, no mess. Only two spaces after the country and the city codes. That's what we're going to try and make them all look like.
# 
# But first, let's correct the street names. The following little function will update the names according to a pre-specified mapping:

# In[3]:

mapping = { "Str.": u"Stra\xdfe",
            "Strasse": u"Stra\xdfe",
            "Str": u"Stra\xdfe",
            "str": u"stra\xdfe",
            "str.": u"stra\xdfe",
            "strasse": u"stra\xdfe"
            }

def update_name(name, mapping):
    '''
    If a street name is inappropriately abbreviated or not properly capitalized, fix it
    '''
    for key in mapping.keys():
        if name.endswith(key):
            name = name.replace(key, mapping[key])
    if name[0].islower():
        name = name.capitalize()
    return name

street_list_upd = set([])
for street in street_list:
    street_list_upd.add(update_name(street, mapping))
    
pp.pprint(street_list_upd)


# Now let's get to those phone numbers. This is going to be a bit trickier.
# 
# I'll try my best with the following function. It should catch all landline numbers, but any mobiles will have their mobile operator code not separated by a white space. There are just too many different ones to take them all into account. Still, it's good enough for me.

# In[23]:

def update_phone_num(num):
    '''
    Strip phone number of all non-numeric characters, then bring it to the standard format of "+49 30 1234567"
    (or as close to it as possible)
    '''
    num = re.sub('[^0-9]','', num)
    if num.startswith('0049'):
        num = '+' + num.lstrip('00')
    if not num.startswith('49'):
        if num.startswith('0'):
            num = '+49 ' + num.lstrip('0')
        else:
            num = '+49 ' + num
    else:
        num = '+49 ' + num.lstrip('49')
    if '30' in num:
        num_spl = num.split('30', 1)
        if len(num_spl[0]) <= 5:
            num = num_spl[1]
            num = '+49 30 ' + num
            return num
        else:
            return num
    else:
        return num

for num in list(street_phone_list[1])[:30]:
    print update_phone_num(num)


# Looks much better.
# 
# Having tidied the data up a bit, it's now time to create csv files that will be imported into the database.

# In[24]:

NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

# Make sure the fields order in the csvs matches the column order in the sql table schema
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']


def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS, default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict"""

    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    tags = []  # Handle secondary tags the same way for both node and way elements

    for tag in element.iter("tag"):
        if tag.get("k") == "addr:street":
            d = {"id": element.get("id"),
                 "value": update_name(tag.get("v"), mapping)}
        elif tag.get("k") == "phone":
            d = {"id": element.get("id"),
                 "value": update_phone_num(tag.get("v"))}
        else:
            d = {"id": element.get("id"),
                 "value": tag.get("v")}
        check = PROBLEMCHARS.search(tag.get("k"))
        if not check:
            m = LOWER_COLON.search(tag.get("k"))
            if m:
                sp = tag.get("k").split(":", 1)
                d["type"] = sp[0]
                d["key"] = sp[1]
            else:
                d["type"] = "regular"
                d["key"] = tag.get("k")
        tags.append(d)
    
    if element.tag == 'node':
        for attr in node_attr_fields:
            node_attribs[attr] = element.get(attr)
        return {'node': node_attribs, 'node_tags': tags}
    elif element.tag == 'way':
        for attr in way_attr_fields:
            way_attribs[attr] = element.get(attr)
        pos = 0
        for nd in element.iter("nd"):
            d = {"id": element.get("id"),
                 "node_id": nd.get("ref"),
                 "position": pos}
            way_nodes.append(d)
            pos += 1
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}


# ================================================== #
#               Helper Functions                     #
# ================================================== #
def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()

class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# ================================================== #
#               Main Function                        #
# ================================================== #
def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

    with codecs.open(NODES_PATH, 'w') as nodes_file,          codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file,          codecs.open(WAYS_PATH, 'w') as ways_file,          codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file,          codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                if validate is True:
                    validate_element(el, validator)

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])

process_map(OSMFILE, validate=False)


# This gives me the csv files which I then manually import into an sqlite database through the sqlite command line tool. 
# 
# First, I create the corresponding tables according to the schema found in p3_osm_schema.sql. Then I import the csv's with .mode csv and .import.
# 
# # And now: Query time!
# 
# There's a convenient way to talk to databases using the python's sqlite3 module.
# 
# First stop, database size (I had to actually google this, as it proved to be not very straightforward).

# In[5]:

import sqlite3 as sql

con = sql.connect('p3_osm_data.db')

with con:
    cur = con.cursor()
    
    cur.execute('PRAGMA PAGE_SIZE')
    page_size = cur.fetchone()
    cur.execute('PRAGMA PAGE_COUNT')
    page_count = cur.fetchone()
    
    size = int(page_size[0]) * int(page_count[0])
    
    print 'Database size is ' + str(size) + ' bytes'
    print 'That is roughly ' + str(round(size / float(1000000) ,1)) + ' Mb'


# Nice, matches what my OS tells me.
# 
# Now, some descriptives.

# In[6]:

N_NODES = 'SELECT COUNT(*) FROM nodes;'
N_WAYS = 'SELECT COUNT(*) FROM ways;'
N_UNIQUE_USERS = '''
                SELECT COUNT(DISTINCT(e.uid))          
                FROM (SELECT uid FROM nodes UNION ALL SELECT uid FROM ways) e;
                '''
TOP_10_AMENITIES = '''
                   SELECT value, COUNT(*) as num
                   FROM nodes_tags
                   WHERE key='amenity'
                   GROUP BY value
                   ORDER BY num DESC
                   LIMIT 10;
                   '''

with con:
    cur = con.cursor()
    
    cur.execute(N_NODES)
    n_nodes = cur.fetchone()
    
    cur.execute(N_WAYS)
    n_ways = cur.fetchone()
    
    cur.execute(N_UNIQUE_USERS)
    n_unique_users = cur.fetchone()
    
    cur.execute(TOP_10_AMENITIES)
    top_10_amen = cur.fetchall()
    
    print 'Number of nodes: ', n_nodes[0]
    print 'Number of ways: ', n_ways[0]
    print 'Number of unique users: ', n_unique_users[0]
    print '\n    Top 10 amenities in the region, by number: '
    for amen in top_10_amen:
        print amen[0], str(amen[1])


# Ok, let's check which cuisines are most popular, and also which leisure activities.

# In[7]:

CUISINES = '''
          SELECT nodes_tags.value, COUNT(*) as num
          FROM nodes_tags 
              JOIN (SELECT DISTINCT(id) 
                  FROM nodes_tags 
                  WHERE value='restaurant'
                      OR value='fast_food'
                      OR value='cafe') i
              ON nodes_tags.id=i.id
          WHERE nodes_tags.key='cuisine'
          GROUP BY nodes_tags.value
          ORDER BY num DESC
          LIMIT 10;
          ''' 
LEISURE = '''
         SELECT nodes_tags.value, COUNT(*) as num
         FROM nodes_tags 
             JOIN (SELECT DISTINCT(id) 
                 FROM nodes_tags) i
             ON nodes_tags.id=i.id
         WHERE nodes_tags.key='leisure'
         GROUP BY nodes_tags.value
         ORDER BY num DESC
         LIMIT 10;
         ''' 

with con:
    cur = con.cursor()
   
    cur.execute(CUISINES)
    cuisines = cur.fetchall()
    
    cur.execute(LEISURE)
    leisure = cur.fetchall()
    
    print "    Most popular cuisines in restaurants, cafes, and fast-foods, by number:"
    for thing in cuisines:
        print thing[0], str(thing[1])
    print "\n    Most popular leisure activities, by number:"
    for thing in leisure:
        print thing[0], str(thing[1])


# Apart from all the playgrounds (and 5 hackerspaces!), there are 152 "pitches". OpenStreetMap wiki says that pitches are all sorts of public places where sports are played. So let's see which sports you can play in the streets of north-eastern Berlin.

# In[8]:

SPORTS = '''
          SELECT nodes_tags.value, COUNT(*) as num
          FROM nodes_tags 
              JOIN (SELECT DISTINCT(id) 
                  FROM nodes_tags 
                  WHERE value='pitch') i
              ON nodes_tags.id=i.id
          WHERE nodes_tags.key='sport'
          GROUP BY nodes_tags.value
          ORDER BY num DESC
          LIMIT 10;
          ''' 
with con:
    cur = con.cursor()
    
    cur.execute(SPORTS)
    sports = cur.fetchall()

    print "    Most popular sports in public places:"
    for thing in sports:
        print thing[0], str(thing[1])


# No surprise there. Table tennis is the national sport in Germany. That's right, not soccer. The number of basketball courts is somewhat surprising though.
# 
# # Further exploration
# 
# Now, one thing I noticed about these data is that street names appear to be not only in the tags with the "street" key, but also in other, non-address tags with the "name" key. According to the OpenStreetMap wiki, this key should describe the "name of a place". Putting the street name there seems non-obvious to me. So I wanted to see if my suspicion was correct and somebody systematically mis-tagged street names.

# In[9]:

STREET_STR = '''
            SELECT value
            FROM ways_tags
            WHERE key = 'street'
            GROUP BY value
            ORDER BY value
            LIMIT 10;
            '''

NAMES_DUPL = '''
        SELECT a.key, b.key, a.value
        FROM ways_tags as a, ways_tags as b
        WHERE a.value = b.value
            AND a.key = 'street'
            AND b.key = 'name'
        GROUP BY a.value
        ORDER BY a.value
        LIMIT 10;
        '''

STR_IN_NAMES_ONLY = '''
                    SELECT value
                    FROM ways_tags
                    WHERE key = 'name'
                        AND instr(value, 'str') > 0
                        AND value NOT IN (SELECT value FROM ways_tags WHERE key='street')
                    GROUP BY value
                    ORDER BY value
                    LIMIT 10;
                    '''

STR_IN_NAMES_ONLY_COUNT = '''
                        SELECT COUNT(DISTINCT value)
                        FROM ways_tags
                        WHERE key = 'name'
                            AND instr(value, 'str') > 0
                            AND value NOT IN (SELECT value FROM ways_tags WHERE key='street');
                        '''

with con:
    cur = con.cursor()
    
    cur.execute(STREET_STR)
    street_str = cur.fetchall()
    
    cur.execute(NAMES_DUPL)
    names_dupl = cur.fetchall()
    
    cur.execute(STR_IN_NAMES_ONLY)
    str_in_names_only = cur.fetchall()
    
    cur.execute(STR_IN_NAMES_ONLY_COUNT)
    str_in_names_only_count = cur.fetchone()
    
    print "\n    Streets in 'street':"
    for thing in street_str:
        print thing[0]
    print "\n    Street name duplicates:"
    for thing in names_dupl:
        print thing[0], thing[1], thing[2]
    print "\n    Street names only in 'name' key, but not in the actual 'street' key?"
    for thing in str_in_names_only:
        print thing[0]
    print "\n    How many of these are there?"
    print str_in_names_only_count[0]


# # Concluding remarks and other suggestions
# 
# So my suspicions appear to have been correct. There are both duplicate streets with "street" and "name" keys, and some street names that only appear with "name" keys. I'm not sure what's going on here, but it seems like these latter streets could use some re-tagging. 
# 
# Such task would be somewhat complex however. I can imagine devising a look-up list of street names which will then be used to filter street names from everything else under the "name" key. But, it would not be a matter of just finding strings containing some characteristic sub-strings (like the expected street types I used in my audit), because of all the other weirdly named streets (e.g. "Zur Waage" - "To the Scale"). One could start by cleaning up all the duplicates though.
# 
# On the other hand, there appear to be a lot of street names not tagged "street". Maybe there's something else going on? One idea is that they are still mis-tagged, and it may be a couple of users (or even one, maybe a bot), who's consistently mis-tagging street names. Another idea is that it somehow makes sense this way, and we'd have to look at all the other data for these particular objects (e.g. their location) to understand what's going on.
# 
# ### What else could be done to improve the dataset?
# 
# Basically, improving a dataset such as this one can be seen as twofold: 
# 
# 1) Get more data, and 
# 
# 2) Get better data.
# 
# To get more data, one idea would be to use the existing database of Pokestops from the popular game Pokemon Go. These Pokestops represent different objects in the public space, which would be a nice addition to OpenStreetMap. However, although such addition would definitely enrich our dataset, proper input can prove tricky, as the objects are sometimes wildly different (e.g. a fountain, a piece of street art, a historical monument etc.). Merging such data may have to be done manually, or programmatically but human-curated, in order for it to be labeled correctly.
# 
# To get better data, mappers could for instance try to employ drones. The OpenStreetMap wiki says that aerial imaging is one of the few practical sources of accurate mapping information for buildings - so getting more aerial images using drones could prove useful, especially in areas where high-resolution images from other sources are not available. Benefits of this approach are: 
# * it is in the spirit of maker/open source/DIY community
# * it may be the most precise option for mapping buildings and other objects in some areas
# * it's fun!
# 
# On the other hand,
# * extra equipment is involved
# * flying drones may be illegal/difficult/dangerous in some areas
# 
# Either way, there's more that could be done to improve the OpenStreetMap data, and this project has been but a small step in that direction.
