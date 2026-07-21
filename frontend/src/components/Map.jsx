import React, { useEffect, useState, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  useMap,
  Marker,
  Popup,
  GeoJSON,
  Polygon,
  CircleMarker,
} from "react-leaflet";
import {
  GeoSearchControl,
  OpenStreetMapProvider,
  MapBoxProvider,
} from "leaflet-geosearch";
import "leaflet-geosearch/dist/geosearch.css";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import MarkerClusterGroup from "react-leaflet-cluster";
import "react-leaflet-cluster/dist/assets/MarkerCluster.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.Default.css";

const iconCache = {};
//create a custom hook to move the map when user click on the item
function MoveMap({ selectedLocation, markerRef = null }) {
  const map = useMap();

  useEffect(() => {
    if (selectedLocation) {
      map.flyTo([selectedLocation[0], selectedLocation[1]], 18, {
        duration: 1.2,
      });
      map.once("moveend", () => {
        markerRef?.current?.openPopup();
      });
    }
  }, [selectedLocation]);

  return null;
}

function Map({ finalList, countyCenter, locationMove, idPopup }) {
  const [leeCounty, setLeeCounty] = useState(null);
  const markerRef = useRef(null); //useRef to mark the popup id
  const [selectedAddress, setSelectedAddress] = useState(null);
  const [isInside, setIsInside] = useState(false);
  const [addressType, setAddressType] = useState("");
  const [addressList, setAddressList] = useState(null);
  const [searchError, setSearchError] = useState("");
  const timer = useRef(null);
  useEffect(() => {
    fetch("/lee-county.json")
      .then((res) => res.json())
      .then(setLeeCounty);
  }, []);
  const LEECOUNTY_BOUNDARY = [
    [
      [26.78980006125687, -82.272362941444],
      [26.789845555613542, -82.26674734260132],
      [26.78506785591573, -82.24039974363203],
      [26.784682327821244, -82.23903842851749],
      [26.78466547444208, -82.2389791674873],
      [26.7820416567969, -82.22592358399687],
      [26.782041344440042, -82.2232956474719],
      [26.771383695762992, -82.20659552905133],
      [26.771385640979, -82.20647976655594],
      [26.771392588357518, -82.20606614853668],
      [26.771432134382756, -82.20371036771571],
      [26.771451667543054, -82.20254589924075],
      [26.771455409378866, -82.20232270862869],
      [26.770580132044987, -82.06111276257575],
      [26.769557491947527, -81.56583524283978],
      [26.422579371979108, -81.56212541999152],
      [26.42121661767304, -81.65945294404435],
      [26.317535087331482, -81.65801989377533],
      [26.316233491651623, -81.81902174232401],
      [26.330254811084547, -81.84588796417505],
      [26.329835733418385, -82.2449563152756],
      [26.419874753315746, -82.33457334444688],
      [26.6450848069833, -82.42798337825371],
      [26.736154829652275, -82.43157338143331],
      [26.788130900846568, -82.46253412522209],
      [26.78980006125687, -82.272362941444],
    ],
  ];
  //setup the bound
  const leeCountyPoints = LEECOUNTY_BOUNDARY[0];
  const LEECOUNTY_BOUNDS = L.latLngBounds(leeCountyPoints);
  //Check the result inside or outside the polygon
  function checkBound(coordinates) {
    console.log(coordinates);
    const longitude = coordinates[0][0];
    const latitude = coordinates[0][1];
    console.log(longitude, latitude);
    console.log("get into checkbound");
    let count = 0;
    for (let item = 0; item < LEECOUNTY_BOUNDARY[0].length; item++) {
      if (item === LEECOUNTY_BOUNDARY[0].length - 1) break;
      const bigLat =
        LEECOUNTY_BOUNDARY[0][item][0] > LEECOUNTY_BOUNDARY[0][item + 1][0]
          ? LEECOUNTY_BOUNDARY[0][item][0]
          : LEECOUNTY_BOUNDARY[0][item + 1][0];
      const bigLng =
        LEECOUNTY_BOUNDARY[0][item][1] > LEECOUNTY_BOUNDARY[0][item + 1][1]
          ? LEECOUNTY_BOUNDARY[0][item][1]
          : LEECOUNTY_BOUNDARY[0][item + 1][1];

      const smallLat =
        LEECOUNTY_BOUNDARY[0][item][0] > LEECOUNTY_BOUNDARY[0][item + 1][0]
          ? LEECOUNTY_BOUNDARY[0][item + 1][0]
          : LEECOUNTY_BOUNDARY[0][item][0];
      const smallLng =
        LEECOUNTY_BOUNDARY[0][item][1] > LEECOUNTY_BOUNDARY[0][item + 1][1]
          ? LEECOUNTY_BOUNDARY[0][item + 1][1]
          : LEECOUNTY_BOUNDARY[0][item][1];
      console.log(LEECOUNTY_BOUNDARY[0].length, item);

      if (smallLat <= latitude && latitude <= bigLat) {
        const fraction = (bigLat - latitude) / (bigLat - smallLat);

        const intersection = smallLng + fraction * (bigLng - smallLng);

        count = intersection > longitude ? count + 1 : count;
      }
    }
    console.log(count);
    if (count % 2 !== 0) {
      console.log("success");
      setIsInside(true);
      setSelectedAddress([latitude, longitude]);
    } else setIsInside(false);
  }
  //search function
  async function searchAddress(address) {
    const token =
      import.meta.env.VITE_MAPBOX_TOKEN;

    const res = await fetch(
      `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(
        address,
      )}.json?access_token=${token}`,
    );

    const data = await res.json();
    if (data.features.length > 0) {
      console.log(data.features);
      setAddressList(data.features);
      console.log(addressList);
    }
  }
  // Get incident color
  // Color palette keyed by incident nature (first word, lowercase)
  const NATURE_COLORS = {
    disturbance: "#e74c3c",
    assault: "#c0392b",
    theft: "#e67e22",
    burglary: "#d35400",
    traffic: "#3498db",
    suspicious: "#9b59b6",
    medical: "#1abc9c",
    fire: "#e74c3c",
    welfare: "#27ae60",
    domestic: "#c0392b",
    default: "#7f8c8d",
  };
  //helper function to get the incident color
  function getIncidentColor(type) {
    const lowerType = type.toLowerCase();
    for (const keyword in NATURE_COLORS) {
      if (lowerType.includes(keyword)) {
        return NATURE_COLORS[keyword];
      }
    }
    return NATURE_COLORS["default"];
  }

  function createIncidentIcon(nature) {
    const color = getIncidentColor(nature);
    if (!iconCache[color]) {
      iconCache[color] = L.divIcon({
        className: "",
        html: `
          <div style="
        width: 18px;
        height: 18px;
        background: ${color};
        border: 2px solid white;
        border-radius: 50%;">
          
          </div>
        `,
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      });
    }
    return iconCache[color];
  }
  return (
    <div style={{ height: "100%", width: "100%", position: "relative" }}>
      <div
        style={{
          height: "40px",
          fontSize: "20px",
          width: "550px",
          borderRadius: "12px",
          paddingLeft: "10px",
          position: "absolute",
          top: "100px",
          left: "calc((100vw - 550px) / 2)",
          zIndex: 1000,
        }}
      >
        <input
          type="text"
          style={{
            height: "40px",
            fontSize: "20px",
            width: "100%",
            borderRadius: "12px",
            paddingLeft: "10px",
            outline: "none",

            zIndex: 1000,
          }}
          placeholder="Enter address"
          value={addressType}
          onChange={(e) => {
            const value = e.target.value;

            setAddressType(value);

            clearTimeout(timer.current);

            if (!value.trim()) return;

            timer.current = setTimeout(() => {
              console.log("CALLING SEARCH:", value);
              searchAddress(value);
            }, 500);
          }}
        />
        {addressType.length !== 0 && (
          <i
            style={{
              fontSize: "20px",
              color: "#222240",
              position: "absolute",
              zIndex: 1000,
              top: "0px",
              left: "94%",
              padding: "10px",
              cursor: "pointer",
            }}
            className="fa-solid fa-xmark"
            onClick={() => {
              setAddressType("");
            }}
          ></i>
        )}
        <ul
          style={{
            width: "500px",
            listStyleType: "none",
            fontSize: "20px",
            position: "absolute",
            zIndex: 1000,
            top: "40px",
            left: "30px",
            cursor: "pointer",
          }}
        >
          {addressList !== null &&
            addressList.map((address, index) => {
              return (
                <li
                  key={index}
                  style={{
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    color: "black",
                    backgroundColor: "white",
                    padding: "10px",
                    borderBottom: "1px solid grey",
                  }}
                  onClick={() => checkBound([address.center])}
                >
                  {address.place_name}
                </li>
              );
            })}
        </ul>
        <div
          style={{
            width: "400px",
            fontSize: "20px",
            position: "absolute",
            zIndex: 1000,
            top: "-40px",
            left: "80px",
            cursor: "pointer",
            color:"black",
            display:"flex",
            justifyContent:"center",
            border:"2px solid red",
            backgroundColor:"white",
            display:"none"
          }}
        >
          {searchError}
        </div>
      </div>

      <MapContainer
        center={countyCenter}
        zoom={10}
        minZoom={10}
        scrollWheelZoom={true}
        style={{ height: "100%", width: "100%" }}
        maxBounds={LEECOUNTY_BOUNDS}
        maxBoundsViscosity={1.0}
      >
        <TileLayer
          className="dark-map"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {/*create a custom hook to move the map when user click on the item */}
        <MoveMap selectedLocation={locationMove} markerRef={markerRef} />
        {leeCounty && (
          <GeoJSON data={leeCounty} style={{ color: "red", weight: 4 }} />
        )}
        {/* <SearchAddress
        setSelectedAddress={setSelectedAddress}
        checkBound={checkBound}
      /> */}
        {isInside ? (
          <MoveMap selectedLocation={selectedAddress} />
        ) : (
          <div className=""></div>
        )}
        ;
        {leeCounty && (
          <Polygon
            positions={[
              [
                [-90, -180],
                [-90, 180],
                [90, 180],
                [90, -180],
                [-90, -180],
              ],
              LEECOUNTY_BOUNDARY,
            ]}
            pathOptions={{
              fillColor: "black",
              fillOpacity: 0.4,
              stroke: false,
            }}
          />
        )}
        <MarkerClusterGroup disableClusteringAtZoom={16}>
          {finalList.map((incident, index) => (
            <Marker
              key={incident.id}
              position={[incident.lat, incident.lng]}
              icon={createIncidentIcon(incident.nature)}
              ref={idPopup === incident.id ? markerRef : null}
            >
              <Popup>
                <div className="popup-address">
                  <h3>{incident.address}</h3>
                  <h5>{incident.city}</h5>
                </div>
                <div className="popup-line"></div>
                <div className="popup-content">
                  <h4 className="popup-content-normal">{`Incident Number: ${incident.incidentNumber}`}</h4>
                  <h4 className="popup-content-normal">
                    Type:
                    <span
                      style={{ fontSize: "16px", color: "#ca745f" }}
                    >{` ${incident.nature}`}</span>
                  </h4>
                  <h4 className="popup-content-normal">{`Disposition: ${incident.disposition}`}</h4>
                  <h4 className="popup-content-normal">{`Date: ${incident.occuredDate.split(".")[0]}`}</h4>
                </div>
              </Popup>
            </Marker>
          ))}
        </MarkerClusterGroup>
      </MapContainer>
    </div>
  );
}

export default Map;
