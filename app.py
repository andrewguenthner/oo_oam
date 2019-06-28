# This code is also really heavily commented, because this is project is likely
# to use a wide variety of volunteer maintainers, it may change hands many
# times, other docs may get lost, and many of the volunteers may not have
# a lot of Python or Flask experience.  So, please excuse the verbosity, and,
# when adding comments, please err on the side of verbosity.

# The libraries are intentionally minimized so that we can deploy without 
# a complex environment
import requests
from flask import Flask, render_template, jsonify
import pandas as pd 

app = Flask(__name__)

# The function below courtesy of Geoff Boeing
# Urban planning professor at Northeastern University
# published at https://geoffboeing.com/2015/10/exporting-python-data-geojson/

def df_to_geojson(df, properties, lat='latitude', lon='longitude'):
    """Generates geojson file from DataFrame, pass column names for properties
    as a list"""

    geojson = {'type':'FeatureCollection', 'features':[]}
    for _, row in df.iterrows():
        feature = {'type':'Feature',
                   'properties':{},
                   'geometry':{'type':'Point',
                               'coordinates':[]}}
        feature['geometry']['coordinates'] = [row[lon],row[lat]]
        for prop in properties:
            feature['properties'][prop] = row[prop]
        geojson['features'].append(feature)
    return geojson

# This is the Flask part of the app.  
@app.route("/")
def greetings():
    """Displays main page"""
    return render_template("index.html")

@app.route("/get_mural_data")
def get_mural_data():
    """Retrieves mural data by parsing data delivered by web request.  Calls 
    df_to_geojson to return data as a geojson object"""
    # Default to an empty object to return
    mural_data = dict()
    # Last checked 27 June 2019 -- should be a page listing all murals in 
    # the Oakland LocalWiki
    url = 'https://localwiki.org/oakland/Murals'
    # Retrieve the page via http
    response = requests.get(url)
 
    # Processing section
    # Init data holders
    mural_names = []
    lats = []
    lons = []
    first_snippet = True #Flag for discarding the first part of the page

    # The text is split at the "GEOMETRYCOLLECTION" keyword. Following the key
    # word are lat and lon coordinates inside keywords such as Point, Polygon,
    # Linestring.  Following this is an <a> tag that we can use for a breakpoint.
    # After the tag, the mural name is given so that also can be collected.

    for snippet in response.text.split('["SRID=4326;GEOMETRYCOLLECTION ('):
        # Skip first snippet that comes before any GEOMETRYCOLLECTION is found
        if first_snippet:
            first_snippet = False
            continue
        else:
            # Text parsing
            # Split at tag  ... forming two pieces [0] and [1]
            temp_split = snippet.split('>')
            # The last part [1] is the name, after lopping off the final three 
            # characters, which are '</a' (the left-over part of the tag closure)
            mural_name = temp_split[1][0:-3]
            # The part before the tag wil be a lon and lat
            # These are just given as two numbers separated by a space
            # Conveniently, the longitude will always be negative, so 
            # we can count on the '-' sign as a more reliable indicator than 
            # a space as to where the longitude starts.  Because the longitude
            # comes first, this also conveniently lets us know where the coordinates
            # we want start, so we split at the '-' 
            geo1 = temp_split[0].split('-')
            # Upon splitting, item [0] will be whatever preceding stuff
            # mostly parentheses, that we don't want, so ignore it.  
            # Item [1] will have a number (stripped of a minus sign) followed 
            # by a space followed by another number and possibly more.
            # So, if we split item [1] at the space, we will get the longitude 
            # at the new item 0, and the latitude (plus some extra) at item [1]
            geo2 = geo1[1].split(' ')
            # We just need to convert the longitude to a number and multiply
            # by -1 to put back the negative sign that got stripped off
            lon = float(geo2[0]) * -1
            # For the latitude, we might get some extra characters at the 
            # end such as  ) " , -- so we will strip these from the right
            # It is tricky to format, but we need ) " and , in single quotes
            # as the argument for rstrip()
            lat = float(geo2[1].rstrip('),"'))
            # Now that we got everything, just append each one
            mural_names.append(mural_name)
            lats.append(lat)
            lons.append(lon)
    # This procedure gets applied for all the GEOMETRYCOLLECTION objects
    # The final object is where we should check for issues, but because 
    # a geometry collection always needs at least two numbers and an <a>
    # tag in this context, all the rest gets thrown out when splitting on 
    # '>', so it works well.  

    # Now, take these lists and make a Pandas DataFrame
    # The coordinates need to be in two colums called 'latitude' and 
    # 'longitude' for the geojson generator to work properly
    mural_df = pd.DataFrame({'name':mural_names,
                             'latitude':lats,
                             'longitude':lons})
    # Now we need to add columns to the DataFrame to capture the
    # properties needed for the OAM maps software.  These properties 
    # include an 'id', 'name', 'address', 'zoom', 'icon', 'popup', 
    # 'link', 'blank', and 'maps'

    # 'name' is already done from the mural name
    
    # The 'id' needs to be a sequence.  To avoid conflicts with other
    # map markers, the number range 10001 - 19999 is reserved for this purpose.

    # First, get the list length
    list_length = len(mural_names)
    # Generate a list of each number starting at 10001
    id_list = [num for num in range(10001,10001+list_length)]
    # Now, add the list to the DataFrame
    mural_df['id'] = id_list

    # The 'address' is required but not available.  We don't want to just
    # leave it blank because a geocoder might get ahold of it, so we want
    # to give it something that won't lead a user too far astray.
    # We'll use 'Oakland, CA' -- pandas will broadcast to each row of the 
    # dataframe
    mural_df['address'] = 'Oakland, CA'

    # 'zoom' is a default map zoom setting.  For the OAM mapper, 13 works
    # well as a default
    mural_df['zoom'] = 13

    # 'icon' needs to be a file name.  OAM uses 'mural_icon.png'  
    mural_df['icon'] = 'mural_icon.png'

    # 'popup' controls what goes in the pop-up when the marker is selected
    # We will just use the name
    mural_df['popup'] = mural_names

    # 'link' controls the link to be displayed.  For now, we'll just use the
    # LocalWiki source page
    mural_df['link'] = url

    # 'blank' is an internal indicator for the OAM software.  We think it is
    # needed for proper transparency, but unsure.  We do know that 1 works.
    mural_df['blank'] = 1

    # 'maps' is a configuration variable to tell the OAM software which map to
    # put the markers on.  Map #20 is currently used.
    mural_df['maps'] = 20

    # Now that the DataFrame is complete, we can turn it into geojson
    # We will make a list of all the properties column names
    props = ['id','name','address','zoom','icon','popup','link','blank','maps']
    # Now just call the function with the df and props names as arguments
    mural_data = df_to_geojson(mural_df, props)

    # Last step, we 'jsonify' the data for output to the client, which will be 
    # a Javascript routine on index.html
    return jsonify(mural_data)


if __name__ == '__main__':
    app.run()