import React from "react";
import trafficLight from "../assets/icon/traffic-light-pole.svg";
import pineLeft from "../assets/icon/pine-left-side.svg";
import pineright from "../assets/icon/pine-right-side.svg";
import treeLeft from "../assets/icon/tree-left-side.svg";
import treeRight from "../assets/icon/tree-right-side.svg";
function LandingPage() {
  return (
    <div className="page-wrapper">
      <div className="page-1">
        <div className="page-1-left">
          <div className="page1-block-top-left">
            <img
              src={pineLeft}
              alt="traffic light"
              style={{height:"80px", top: "80px", left: "45" }}
              className="icon"
            />
            <img
              src={trafficLight}
              alt="traffic light"
              style={{ top: "-60px", left: "70%" }}
              className="traffic-light"
            />
            <img
              src={trafficLight}
              alt="traffic light"
              style={{ top: "-60px", left: "70%" }}
              className="traffic-light"
            />
            <img
              src={trafficLight}
              alt="traffic light"
              style={{ top: "-60px", left: "70%" }}
              className="traffic-light"
            />
          </div>
          <div className="page1-block-bottom-left">
            <img
              src={trafficLight}
              alt="traffic light"
              style={{ top: "-60px", left: "70%" }}
              className="traffic-light"
            />
          </div>
        </div>
        <div className="page-1-right">
          <div className="page1-block-right"></div>
        </div>
      </div>
      <div className="page-2">
        <div className="page-2-left">
          <div className="page2-block-left"></div>
        </div>
        <div className="page-2-right">
          <div className="page2-block-right"></div>
        </div>
      </div>
      <div className="page-3">
        <div className="page-3">
          <div className="page-3-left">
            <div className="page3-block-top-left"></div>
            <div className="page3-block-bottom-left">
              <img
                src={trafficLight}
                alt="traffic light"
                style={{ top: "-60px", left: "70%" }}
                className="traffic-light"
              />
            </div>
          </div>
          <div className="page-3-right">
            <div className="page3-block-top-right"></div>
            <div className="page3-block-bottom-right"></div>
          </div>
        </div>
      </div>
      <div className="page-4"></div>
    </div>
  );
}

export default LandingPage;
