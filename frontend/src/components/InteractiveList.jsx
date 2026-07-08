import React, { useState } from "react";
import "./InteractiveList.css";
function InteractiveList({ finalList,finalListUnlocated, getLocation }) {
  const [isLocated, setIsLocated] = useState(true);
  const [selectedItem, setSelectedItem] = useState(null);
  
  return (
    <div className="list">
      <div className="list-selection">
        <div
          className={
            isLocated
              ? "selection-located selection-showTab selection-shadow-right"
              : "selection-located"
          }
          onClick={() => setIsLocated(true)}
        >
          Located
        </div>
        <div
          className={
            !isLocated
              ? "selection-unlocated selection-showTab selection-shadow-left"
              : "selection-unlocated"
          }
          onClick={() => setIsLocated(false)}
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
        />
        {/* <button className="list-search-btn">Search</button> */}
      </div>
      <div className="list-board">
        {isLocated?finalList.map((incident, index) => (
          <div key={incident.id} className={selectedItem === incident.id?"list-board-item item-selected-border":"list-board-item"}
          onClick={()=>{
            setSelectedItem(incident.id)
            getLocation(incident.lat,incident.lng);}}>
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
        )):
        finalListUnlocated.map((incident, index) => (
          <div key={incident.id} className={selectedItem === incident.id?"list-board-item item-selected-border":"list-board-item"}
          onClick={()=>{setSelectedItem(incident.id)}}>
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
        
        }
      </div>
      
    </div>
  );
}

export default InteractiveList;
