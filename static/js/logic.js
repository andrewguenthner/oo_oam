// Creating map object
const muralMap = L.map("test-map", {
  center: [37.8, -122.25],
  zoom: 11.5
});

// Adding tile layer to the map
L.tileLayer("https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}", {
  attribution: "Map data &copy; <a href=\"https://www.openstreetmap.org/\">OpenStreetMap</a> contributors, <a href=\"https://creativecommons.org/licenses/by-sa/2.0/\">CC-BY-SA</a>, Imagery © <a href=\"https://www.mapbox.com/\">Mapbox</a>",
  maxZoom: 15,
  id: "mapbox.streets",
  accessToken: API_KEY
}).addTo(muralMap);

// Listen for the button press, then grab data

d3.select("#update_mural").on("click",  function(e){

const url = "/get_mural_data"
d3.json(url).then( function (muralData) {

  // Create a new marker cluster group
  const markers = L.markerClusterGroup({
      maxClusterRadius: 40
  });

  // Loop through data
  for (var i = 0; i < muralData.features.length; i++) {

    // Set the data location property to a variable
    const location = muralData.features[i].geometry;

    // Check for location property
    if (location) {
      // Add a new marker to the cluster group and bind a pop-up
      markers.addLayer(L.marker([location.coordinates[1], location.coordinates[0]])
        .bindPopup(muralData.features[i].properties.name));
            }
        }; // end of data loop

    // Add our marker cluster layer to the map
    muralMap.addLayer(markers);

    // Modify the instructions area to let user know how to determine success
    d3.select("#instructions").text("Look at the map below.  If markers have appeared (they may be circles with numbers in them if clustered) then \
        your data is ready to download.  If not, please contact the site admin (click on upper left corner \
        of page, then navigate to 'contact').");
    
    // If user indicates success by clicking button ...
    d3.select("#download_button").on("click", function(e) {
        // convert muralData from JSON into Blob,
        const muralFileData = new Blob([JSON.stringify(muralData)],{type:'application/json'});
        // create a URL for the Blob so that it can be downloaded
        const urlForFile = window.URL.createObjectURL(muralFileData);
        // Add the URL to the download button
        document.getElementById("download_button").href = urlForFile;

    });

    }); // end of asynchronous response

}); // end of event listener