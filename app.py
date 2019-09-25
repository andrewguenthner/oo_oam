# This code is also really heavily commented, because this is project is likely
# to use a wide variety of volunteer maintainers, it may change hands many
# times, other docs may get lost, and many of the volunteers may not have
# a lot of Python or Flask experience.  So, please excuse the verbosity, and,
# when adding comments, please err on the side of verbosity.

# The libraries are intentionally minimized so that we can deploy without 
# a complex environment
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, jsonify
import pandas as pd 
import time 
import re

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
    response = requests.get(url).text
 
    # Processing section
    # Init data holders
    base_url = 'https://localwiki.org/oakland/'
    site_url = 'https://localwiki.org'
    mural_names = []
    mural_links = []
    lats = []
    lons = []
    first_snippet = True #Flag for discarding the first part of the page

    # The text is split at the "GEOMETRYCOLLECTION" keyword. Following the key
    # word are lat and lon coordinates inside keywords such as Point, Polygon,
    # Linestring.  Following this is an <a> tag that we can use for a breakpoint.
    # After the tag, the mural name is given so that also can be collected.

    for snippet in response.split('["SRID=4326;GEOMETRYCOLLECTION ('):
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
            # To grab the link, we take the first part, split it at '/oakland/', which is where
            # the path starts, take the part after that, and leave out the last two characters (\")
            # This string is added to the LocalWiki base_url
            mural_link = base_url + temp_split[0].split('/oakland/')[1][:-2]
            # To get the coordinates, we'll go "back a step" to temp_split
            # TODO:  Improve this to not go backwards!
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
            mural_links.append(mural_link)
            lats.append(lat)
            lons.append(lon)
    # This procedure gets applied for all the GEOMETRYCOLLECTION objects
    # The final object is where we should check for issues, but because 
    # a geometry collection always needs at least two numbers and an <a>
    # tag in this context, all the rest gets thrown out when splitting on 
    # '>', so it works well.  

    # We now need to get images for each mural on the list.  
    # These will be converted to html for the pop-ups that will appear for each mural
    # The pop-up html will be stored in a list called popup_list
    # We will also keep a list of murals that will be put in the reserved map because
    # they are not available for viewing
    popup_list = []
    put_on_reserve_list = []
    # We can conveniently use all the links we just gathered to visit pages one by one
    # but we will need their index to match things like thier name
    for ix, mural_page in enumerate(mural_links):
        # Grab page data
        page_data = requests.get(mural_page).text
        # Deliberately slow down the process so as not to overwhelm LocalWiki with requests
        time.sleep(0.5)
        print(f'Getting page {ix}')
        # BeautifulSoup will take the page data and parse it very conveniently for us
        soup = BeautifulSoup(page_data, 'html.parser')
        # First, we will look for any Wiki tag that OAM has left on the page
        # Wiki tags with text that starts with 'oam_uses_' should include the name of an image
        # that they would like to use.  
        # Wiki tags that start with 'not currently visible' should be put on the reserve map
        # Wiki tags are found in list item (li) html tags, with a class of 'tag', that is,
        # <li class="tag">... to find these, we just pass a keyword argument (class_, because
        # 'class' itself is a reserved word), to the Beautiful Soup find_all function
        page_tags = soup.find_all('li', class_='tag')
        # Default to not use favored image
        use_favored_image = False
        mural_not_visible = False
        artist_found = False
        artist_name = None
        artist_link = None
        # If no Wiki tags were found, the for loop will be skipped
        for page_tag in page_tags: #page_tag is a Beautiful Soup object, with many helpful featuers
            tag_text = page_tag.text  # a convenient Beautiful Soup attribute 
            if tag_text[0:9].lower() == 'oam_uses_':  # Check for the special OAM prefix, ignoring case
                favored_image_name = tag_text[10:] # What follows the prefix should be a name
                if favored_image_name is not None:
                    use_favored_image = True
            if tag_text[0:21] == 'not currently visible':
                    mural_not_visible = True
            if tag_text[0:6] == 'artist':
                artist_name = tag_text[7:].lstrip().rstrip()
                if artist_name is not None:
                    artist_found = True
                    for target_tag in page_tags:
                        if target_tag.text.lower().lstrip().rstrip() == artist_name.lower().lstrip().rstrip():
                            artist_link = 'https://localwiki.org/oakland/tags/' + target_tag.text.lower().replace(' ','')

        #Append True or False to put_on_reserve_map_list
        put_on_reserve_list.append(mural_not_visible)
        # Now we will collect the image info
        # We wukk start by putting 'None' in link_for_image, to track if we've found anything
        link_for_image = None
        # The image names are stored in <span class="image_frame image_frame_border" tags
         # We can search using just 'image_frame' for the class thanks to Beautiful Soup
        image_tags = soup.find_all('span',class_='image_frame')
        # First case, if a favored image is found
        if use_favored_image:
            # If the name has a file suffix (e.g. '.jpg', we will ignore it)
            # We do that by splitting at the dot and taking everything prior
            favored_image_name = favored_image_name.split('.')[0]
            # Within these tags, the name we want to search for will be inside the <a> tag
            # so we search through image_tags one at a time, see if there are any <a> tags
            # where the href contains the favored_image_name (using regular expressions),
            # and, if so, assign the <img> tag's src attribute to the image link and the 
            # matching tag's href attribute to the info link, then stop searching
            for image_tag in image_tags:
                matching_tag = image_tag.find('a',href=re.compile(favored_image_name)) 
                if matching_tag is not None:
                    link_for_image = site_url + matching_tag.img['src']
                    link_for_img_info = site_url + matching_tag['href']
                    break
        # This part will be triggered if we found nothing even though a favored image
        # was specified, or if no favored image was specified
        if link_for_image is None: 
            # Just use the first image by default (use try to exclude cases where there is no image)
            # To get it, take the first a tag, then first img tag, then the src attribute value
            # In addition, the info page will be the first tag's <a> href attribute.
            # All very easy to do with Beautiful Soup 
            try:
                link_for_image = site_url + image_tags[0].a.img['src']
                link_for_img_info = site_url + image_tags[0].a['href']
            except (TypeError, IndexError): #happens if no image tags are located, use default urls
                link_for_image = 'https://upload.wikimedia.org/wikipedia/commons/a/ac/No_image_available.svg'
                link_for_img_info = 'https://localwiki.org/oakland/Murals'


        # Now we will put the mural name, link, and image link in pop-up text
        # according to a pre-specified format
        popup_text_string = f'<a href="{mural_page}" target="blank">'
        popup_text_string += f'{mural_names[ix]}</a><br>'
        if artist_found:
            if (artist_link is not None):
                popup_text_string += f'by <a href="{artist_link}" target="blank">{artist_name}</a><br>'
            else:  # artist found, but no link found
                popup_text_string += f'by {artist_name}<br>'
        else:   # artist not found 
            popup_text_string += f'Help us <a href="https://andrewguenthner.com/help-oakland-art-murmur-identify-mural-artists/" target="blank">give credit</a> to the artist.<br>'
        popup_text_string += f'<a href="{link_for_img_info}" target="blank">'
        popup_text_string += f'<img src="{link_for_image}"></a><br>'
        popup_text_string += f'<a href="{mural_page}" target="blank">More info&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        popup_text_string += f'</a><a href="{link_for_img_info}" target="blank">Larger image</a>'
        popup_list.append(popup_text_string)
    # This ends our big for loop (visitng all pages to get info)
    
    # For test purposes only, append blank values to popup_list
    popup_list_length = len(popup_list)
    popup_list_missing_length = len(mural_links) - popup_list_length
    if popup_list_missing_length > 0:
        for _ in range(popup_list_missing_length):
            popup_list.append('not collected')
    

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
    # map markers, the number range 101-999 is reserved for this purpose.

    # First, get the list length
    list_length = len(mural_names)
    # Generate a list of each number starting at 101
    id_list = [num for num in range(707,707+list_length)]
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

    # 'icon' needs to be a file name.  OAM uses 'art_blank_t.png'  
    mural_df['icon'] = 'art_black_t.png'

    # 'popup' controls what goes in the pop-up when the marker is selected
    # We will use the list of carefully formatted strings we put together
    mural_df['popup'] = popup_list

    # 'link' controls the link to be displayed. We will keep blank so that
    # users get a popup instead
    mural_df['link'] = ''

    # 'blank' is an internal indicator for the OAM software.  We think it is
    # needed for proper transparency, but unsure.  We do know that 1 works.
    mural_df['blank'] = 1

    # 'maps' is a configuration variable to tell the OAM software which map to
    # put the markers on.  Map #17 is currently for used markers, and map 21
    # is for unused.  We will use put_on_reserve_list converted to int (1 if true, 
    # 0 if false), multiply by 4, then add to 17, so that the list comprehension will
    # generate 17 if put_on_reserve_list is False or 21 if True
    map_list = [17 + 4 * int(list_item) for list_item in put_on_reserve_list]
    mural_df['maps'] = map_list 
    # For custom murals that do not appear on the scraped list but that we want to add,
    # we will import a csv with all the right colums
    try:
        extra_murals_df = pd.read_csv('extra_murals.csv')
        mural_df = mural_df.append(extra_murals_df)
    except IOError:
        pass    # Ignore this step if it generates an error

    # Now what we need to do is reserve space for future mural maps
    # To do this, we'll make a list of dictionaries with the column names as 
    # keys, and then convert to a DataFrame that will be appended to the one
    # we just made
    list_of_dicts_for_reserve = []
    temp_dict = dict()   # Empty temporary dict to append to list
    for num in range (706+len(mural_df),1601):
        temp_dict['name'] = 'reserved'
        temp_dict['latitude'] = 37.8   # This is a stand-in for Oakland
        temp_dict['longitude'] = -122.4  # This puts the marker safely out to sea so no one sees it by accident
        temp_dict['id'] = num
        temp_dict['address'] = 'Oakland, CA'
        temp_dict['zoom'] = 13
        temp_dict['icon'] = 'art_blank_t.png'
        temp_dict['popup'] = 'reserved'
        temp_dict['link'] = 'https://localwiki.org/oakland/Murals'
        temp_dict['blank'] = 1
        temp_dict['maps'] = 21  # This is a map to store the 'reserved' markers
        list_of_dicts_for_reserve.append(temp_dict)
    
    # Convert to DataFrame is now super easy
    reserve_df = pd.DataFrame(list_of_dicts_for_reserve)

    # Now append this to the original DataFrame, note the need for assignment 
    mural_df = mural_df.append(reserve_df)
    
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