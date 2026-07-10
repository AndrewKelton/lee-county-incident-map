import React, { useState } from "react";
import "./InteractiveList.css";
function InteractiveList({ finalList, finalListUnlocated, getLocation, getIncidentID }) {
  const [isLocated, setIsLocated] = useState(true);
  const [selectedItem, setSelectedItem] = useState(null);
  const [searchResult, setSearchResult] = useState("");
  const [filteredList, setFilteredList] = useState(null);
  function filterIncidents(e, finalList, finalListUnlocated) {
    setSearchResult(e);
    const upperCase = e.toUpperCase();

    const filteredList = isLocated
      ? finalList.filter(
          (item) =>
            item.address.includes(upperCase) || item.city.includes(upperCase),
        )
      : finalListUnlocated.filter(
          (item) =>
            item.address.includes(upperCase) || item.city.includes(upperCase),
        );
    console.log(filteredList);
    setFilteredList(filteredList);
  }
  function resetText() {
    setSearchResult("");
    setFilteredList(null);
  }
  return (
    <div className="list">
      <div className="list-selection">
        <div
          className={
            isLocated
              ? "selection-located selection-showTab selection-shadow-right"
              : "selection-located"
          }
          onClick={() => {
            setIsLocated(true);
            resetText();
          }}
        >
          Located
        </div>
        <div
          className={
            !isLocated
              ? "selection-unlocated selection-showTab selection-shadow-left"
              : "selection-unlocated"
          }
          onClick={() => {
            setIsLocated(false);
            resetText();
          }}
        >
          <span className="selection-word">Unlocated</span>
        </div>
        <div
          className={
            !isLocated
              ? "selection-line selection-line-right"
              : "selection-line selection-line-left"
          }
        ></div>
      </div>
      <div className="list-search">
        <input
          type="text"
          style={{
            height: "40px",
            fontSize: "20px",
            width: "80%",
            borderRadius: "12px",
            paddingLeft: "10px",
          }}
          placeholder="Type here to filter incidents..."
          value={searchResult}
          onChange={(e) =>
            filterIncidents(e.target.value, finalList, finalListUnlocated)
          }
        />
        {searchResult.length !== 0 && (
          <i
            class="fa-solid fa-xmark search-delete-icon"
            onClick={resetText}
          ></i>
        )}
      </div>
      {/* 
        --- search result ? ---- yes -> filtered list
                            
                            ---- no -> isLocated? ---- yes -> located list
                                                  ---- no -> unlocated list
      */}
      <div className="list-board">
        {searchResult.length !== 0 //check to see if the search bar has any value to trigger the filter
          ? filteredList.map(
              (
                incident,
                index, //create a filtered list
              ) => (
                <div
                  key={incident.id}
                  className={
                    selectedItem === incident.id
                      ? "list-board-item item-selected-border"
                      : "list-board-item"
                  }
                  onClick={() => {
                    setSelectedItem(incident.id);
                    getLocation(incident.lat, incident.lng);
                    getIncidentID(incident.id);
                  }}
                >
                  <h2
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {incident.address}
                  </h2>
                  <div className="list-board-item-second">
                    <h3>{incident.city}</h3>
                    <span>{incident.occuredDate.split(".")[0]}</span>
                  </div>
                </div>
              ),
            )
          : isLocated //if search bar is emptied, continue working with located and unlocated listing
            ? finalList.map((incident, index) => (
                <div
                  key={incident.id}
                  className={
                    selectedItem === incident.id
                      ? "list-board-item item-selected-border"
                      : "list-board-item"
                  }
                  onClick={() => {
                    setSelectedItem(incident.id);
                    getLocation(incident.lat, incident.lng);
                    getIncidentID(incident.id);
                  }}
                >
                  <h2
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {incident.address}
                  </h2>
                  <div className="list-board-item-second">
                    <h3>{incident.city}</h3>
                    <span>{incident.occuredDate.split(".")[0]}</span>
                  </div>
                </div>
              ))
            : finalListUnlocated.map((incident, index) => (
                <div
                  key={incident.id}
                  className={
                    selectedItem === incident.id
                      ? "list-board-item item-selected-border"
                      : "list-board-item"
                  }
                  onClick={() => {
                    setSelectedItem(incident.id);
                  }}
                >
                  <h2
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {incident.address}
                  </h2>
                  <div className="list-board-item-second">
                    <h3>{incident.city}</h3>
                    <span>{incident.occuredDate.split(".")[0]}</span>
                  </div>
                </div>
              ))}
      </div>
    </div>
  );
}

export default InteractiveList;
