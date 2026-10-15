const urlParam = new URLSearchParams(window.location.search);
const electionId = urlParam.get("electionId");
const electionDesc = urlParam.get("electionDesc");
const scheduleType = urlParam.get("scheduleType");
const mapCenter = [-96.595470, 33.2039830];
const mapZoom = 10;
const electionsApiProxyBaseUrl = 'https://api.collincountytx.gov/Elections2APIProxy';

if (scheduleType != null && scheduleType.toUpperCase() == "EV") {
    $('#pageTitleHead').text(
        $('#pageTitleHead').text().replace('Polling Locations', 'Early Voting Locations')
    );
} else if (scheduleType != null && scheduleType.toUpperCase() == "ED") {
   $('#pageTitleHead').text(
        $('#pageTitleHead').text().replace('Polling Locations', 'Election Day Voting Locations')
    );
}

function ccElectionWaitMapCreate() {
   require([
      "esri/config",
      "esri/views/MapView",
      "esri/Map",
      "esri/layers/FeatureLayer",
      "esri/geometry/Point",
      "esri/widgets/Expand",
      "esri/widgets/Legend",
      "esri/widgets/FeatureTable",
      "esri/widgets/Home",
      "esri/request"
   ], function (esriConfig, MapView, Map, FeatureLayer, Point, Expand, Legend, FeatureTable, Home, esriRequest) {
      esriConfig.apiKey =
         "AAPKf3de335f063c4fb7914fffb9b83f85afItf1Kv2PcYWfbrMrA71NZVeqe_8S-NnGHmmascM0GzjdUPpdJhH39USrwCw9BTU1";

      baseHtml();

      var pollLayer;
      const viewSpatialReference = 3857;

      if (electionId == null || electionId == '' || scheduleType == null || scheduleType == '') {
         var baseElectionUrl = electionsApiProxyBaseUrl + '/elections/public';

         esriRequest(baseElectionUrl, {
            responseType: "json"
         }).then(function (response) {
            var data = response.data || [];

            $("#noElectionId").empty().after('<div class="sampleTitles"></div>');

            data.sort((a, b) => {
               const dateDiff = new Date(a.electionDate).getTime() - new Date(b.electionDate).getTime();

               if (dateDiff !== 0) {
                  return dateDiff;
               }

               const descA = a.electionDescription ?? '';
               const descB = b.electionDescription ?? '';

               return descA.localeCompare(descB);
            });

            $.each(data, function (index, item) {
               var titleLink = $('<a href="javascript:;" class="titleLink" electionID="' + item.electionId + '"></a>')
                  .append(item.electionDescription)
                  .append(" - Early Voting");

               titleLink.on('click', function () {
                  var ballotLink = (window.location.href).split('?')[0];
                  ballotLink = ballotLink + '?electionId=' + item.electionId + "&scheduleType=ev&electionDesc=" + item.electionDescription;
                  window.open(ballotLink, "_self");
               });

               var titleLinkED = $('<a href="javascript:;" class="titleLink" electionID="' + item.electionId + '"></a>')
                  .append(item.electionDescription)
                  .append(" - Election Day");

               titleLinkED.on('click', function () {
                  var ballotLink = (window.location.href).split('?')[0];
                  ballotLink = ballotLink + '?electionId=' + item.electionId + "&scheduleType=ed&electionDesc=" + item.electionDescription;
                  window.open(ballotLink, "_self");
               });

               $('.sampleTitles').append(titleLink).append(titleLinkED);
            });
         });

         document.getElementById("viewDiv").style.display = 'none';
         document.getElementById("tablePlace").style.display = 'none';
         document.getElementById("tableDiv").style.display = 'none';
         document.getElementById("maparea").style.display = 'none';
         document.getElementById("noElectionId").style.display = 'block';
         return;
      } else {
         document.getElementById("noElectionId").style.display = 'none';
         document.getElementById("maparea").style.display = 'block';
      }

      var map = new Map({
         basemap: "topo-vector"
      });

      var view = new MapView({
         container: viewDiv,
         map: map,
         center: mapCenter,
         zoom: mapZoom,
         ui: {
            padding: {
               bottom: 15,
               right: 0
            }
         }
      });

      let homeWidget = new Home({
         view: view
      });

      view.ui.add(homeWidget, "top-left");

      var fields = [
         {
            name: "ObjectID",
            alias: "ObjectID",
            type: "oid"
         },
         {
            name: "pollingLocationId",
            alias: "Polling Location Id",
            type: "integer"
         },
         {
            name: "pollPlace",
            alias: "Polling Place",
            type: "string"
         },
         {
            name: "streetAddress",
            alias: "Street Address",
            type: "string"
         },
         {
            name: "city",
            alias: "city",
            type: "string"
         },
         {
            name: "state",
            alias: "state",
            type: "string"
         },
         {
            name: "zip",
            alias: "zip",
            type: "string"
         },
         {
            name: "directions",
            alias: "dirctions",
            type: "string"
         },
         {
            name: "lat",
            alias: "lat",
            type: "double"
         },
         {
            name: "long",
            alias: "long",
            type: "double"
         },
         {
            name: "alternateName",
            alias: "alternate Name",
            type: "string"
         },
         {
            name: "waitTime",
            alias: "wait time",
            type: "integer"
         },
         {
            name: "displayAddress",
            alias: "displayAddress",
            type: "string"
         },
         {
            name: "displayName",
            alias: "Display Name",
            type: "string"
         }
      ];

      const pTemplate = {
         title: "{displayName}",
         content: waitTimePopup
      };

      const dotSize = 8;

      const simplewaitTimeGraphicRenderer = {
         type: "class-breaks",
         field: "waitTime",
         classificationMethod: "esriClassifyManual",
         legendOptions: {
            title: "Wait Time (min)"
         },
         defaultSymbol: {
            type: "simple-marker",
            color: "black",
            size: dotSize
         },
         defaultLabel: "Closed",
         classBreakInfos: [
            {
               minValue: 41,
               maxValue: 120,
               symbol: {
                  type: "simple-marker",
                  color: "red",
                  size: dotSize
               }
            },
            {
               minValue: 21,
               maxValue: 40,
               symbol: {
                  type: "simple-marker",
                  color: "yellow",
                  outline: {
                     width: 1,
                     color: [0, 0, 0]
                  },
                  size: dotSize
               }
            },
            {
               minValue: 0,
               maxValue: 20,
               symbol: {
                  type: "simple-marker",
                  color: "green",
                  size: dotSize
               }
            }
         ]
      };

      view.when(function () {
         getData()
            .then(checkNull)
            .then(createGraphics)
            .then(createFeatureLayer)
            .then(createPollingList)
            .then(createLegend)
            .catch(errback);
      });

      function baseHtml() {
         const mapPage = document.getElementById("mapPage");
         mapPage.innerHTML = `
         <div id="noElectionId">
         <h4>Map Unavailable</h4>
         <p>There is currently no map available. <a href="/Elections/election-information">Please return to the election
                 information.</a></p>
         </div>
         <div id="maparea" class="map-area">
            <div id="viewDiv"></div>
            <div id="tablePlace">
               <div id="backToList">
                  <span>Select a location to view it on the map.</span>
                  <span class="fullList"><span class="icon-fast-bw"> </span>Show Full List</span>
               </div>
               <h4 class="catRowHead">
                  <div>Location </div>
                  <div>Wait Time </div>
               </h4>
               <div id="tableDiv">
                  <div id="pollPlace">
                  </div>
               </div>
            </div>
         </div>`;
      }

      function checkNull(response) {
         if (response.data !== null) {
            if ((electionDesc != null) && (electionDesc != '')) {
               var subTitleType = '';

               if (scheduleType != null && scheduleType.toUpperCase() == "EV") {
                  subTitleType = $('<span class="scheduletype"></span>').append('Early Voting Map');
               } else if (scheduleType != null && scheduleType.toUpperCase() == "ED") {
                  subTitleType = $('<span class="scheduletype"></span>').append('Election Day Voting Map');
               }

               $('#pageTitle').empty().append(electionDesc);
               $('#pageTitle').after(subTitleType);
            }

            return response;
         } else {
            const divTable = document.getElementById('maparea');
            divTable.textContent = "Coming soon";
            return Promise.reject("Election has no active polling location.");
         }
      }

      function getData() {
         var url = electionsApiProxyBaseUrl + "/elections/public";

         return esriRequest(url, {
            responseType: "json"
         }).then(function (response) {
            var elections = response.data || [];
            var election = elections.find(function (item) {
               return String(item.electionId) === String(electionId);
            });

            if (!election) {
               response.data = null;
               return response;
            }

            var pollingLocations = election.pollingLocations || [];

            response.data = pollingLocations.filter(function (item) {
               if (scheduleType != null && scheduleType.toUpperCase() == "EV") {
                  return item.schedule === "EarlyVoting" || item.schedule === "Both";
               } else if (scheduleType != null && scheduleType.toUpperCase() == "ED") {
                  return item.schedule === "ElectionDay" || item.schedule === "Both";
               }

               return true;
            });

            if (response.data.length === 0) {
               response.data = null;
            }

            return response;
         });
      }

      function createGraphics(response) {
         let jsonData = response.data;

         return jsonData.map(function (feature, i) {
            return {
               geometry: new Point({
                  x: feature.pollingLocation.long,
                  y: feature.pollingLocation.lat
               }),

               attributes: {
                  ObjectID: i,
                  pollingLocationId: feature.pollingLocation.pollingLocationId,
                  pollPlace: feature.pollingLocation.pollPlace,
                  streetAddress: feature.pollingLocation.streetAddress,
                  city: feature.pollingLocation.city,
                  state: feature.pollingLocation.state,
                  zip: feature.pollingLocation.zip,
                  directions: feature.pollingLocation.directions,
                  lat: feature.pollingLocation.lat,
                  long: feature.pollingLocation.long,
                  alternateName: feature.pollingLocation.alternateName,
                  waitTime: feature.pollingLocation.waitTime,
                  displayName: feature.pollingLocation.displayName
               }
            };
         });
      }

      function createFeatureLayer(graphics) {
         pollLayer = new FeatureLayer({
            source: graphics,
            fields: fields,
            outFields: ["*"],
            objectIdField: "ObjectID",
            renderer: simplewaitTimeGraphicRenderer,
            title: "Polling Places",
            labelPlacement: "esriServerPointLabelPlacementAboveCenter",
            popupTemplate: pTemplate,
            spatialReference: {
               wkid: viewSpatialReference
            },
            geometryType: "point"
         });

         map.add(pollLayer);

         pollLayer.orderBy = [
            {
               order: "descending",
               field: "displayName"
            }
         ];

         return pollLayer;
      }

      const county = new FeatureLayer({
         url: "https://services1.arcgis.com/fdWXd5OobWR1E3er/arcgis/rest/services/County_Limit/FeatureServer",
         title: "County Limit",
         outFields: "*",
         displayField: "County"
      });

      map.add(county);

      const labelClass = {
         symbol: {
            type: "text",
            color: "black",
            font: {
               family: "arial",
               size: 10,
               weight: "bold",
               height: "1em"
            },
            yoffset: 2.5
         },
         labelPlacement: "center-center",
         labelExpressionInfo: {
            expression: "If ($feature.waitTime == null)\nreturn null\nElse return $feature.waitTime\n"
         }
      };

      const listNode = document.getElementById("tableDiv");
      let backParent = document.getElementById("backToList");
      const backToListNode = backParent.children[1];

      backToListNode.addEventListener("click", onBackToListClickHandler);

      function onBackToListClickHandler(event) {
         view.goTo({
            center: mapCenter,
            zoom: mapZoom
         });

         view.popup.close();
      }

      function createPollingList(pollLayer) {
         view.whenLayerView(pollLayer).then(function (layerView) {
            layerView.watch("updating", function (value) {
               if (!value) {
                  layerView
                     .queryFeatures({
                        geometry: view.extent,
                        returnGeometry: true,
                        orderByFields: ["displayName"]
                     })
                     .then(function (results) {
                        graphics = results.features;

                        const fragment = document.createDocumentFragment();

                        if (graphics) {
                           graphics.forEach(function (result, index) {
                              const attributes = result.attributes;
                              const name = attributes.displayName;
                              const waitTime = attributes.waitTime;
                              const pollLocation = '<br/>' + attributes.streetAddress + '<br/>' + attributes.city + ', TX ' + attributes.zip;

                              const div = document.createElement("div");
                              div.classList.add("panel-result");
                              div.classList.add("catRowGrp");
                              div.tabIndex = 0;
                              div.setAttribute("data-result-id", index);

                              const nameDiv = document.createElement("div");
                              nameDiv.setAttribute("data-result-id", index);

                              const nameSpanLabel = document.createElement("span");
                              nameSpanLabel.classList.add("catLabel");
                              nameSpanLabel.textContent = "Location: ";

                              const nameSpanText = document.createElement("span");
                              nameSpanText.innerHTML = name + pollLocation;

                              nameDiv.appendChild(nameSpanLabel);
                              nameDiv.appendChild(nameSpanText);

                              const waitTimeDiv = document.createElement("div");
                              waitTimeDiv.setAttribute("data-result-id", index);

                              const waitTimeSpanLabel = document.createElement("span");
                              waitTimeSpanLabel.classList.add("catLabel");
                              waitTimeSpanLabel.textContent = "Wait Time: ";

                              const waitTimeSpanText = document.createElement("span");

                              if (waitTime < 900) {
                                 waitTimeSpanText.innerText = waitTime;
                              } else {
                                 waitTimeSpanText.innerText = "Closed";
                              }

                              waitTimeDiv.appendChild(waitTimeSpanLabel);
                              waitTimeDiv.appendChild(waitTimeSpanText);

                              div.appendChild(nameDiv);
                              div.appendChild(waitTimeDiv);

                              fragment.appendChild(div);
                           });
                        } else {
                           fragment.textContent = "Coming soon";
                        }

                        listNode.innerHTML = "";
                        listNode.appendChild(fragment);
                     })
                     .catch(function (error) {
                     });
               }
            });
         });
      }

      listNode.addEventListener("click", onListClickHandler);

      function onListClickHandler(event) {
         const target = event.target;

         if (target.hasAttribute("data-result-id")) {
            var resultId = target.getAttribute("data-result-id");
         } else {
            var resultId = target.parentNode.getAttribute("data-result-id");
         }

         const result = resultId && graphics && graphics[parseInt(resultId, 10)];

         if (result) {
            view
               .goTo({
                  target: result,
                  zoom: 15
               })
               .then(function () {
                  view.popup.open({
                     features: [result],
                     popupTemplate: pTemplate,
                     alignment: "top-center",
                     location: result.geometry.centeroid
                  });

                  view.popup.collapseEnabled = false;
               })
               .catch(function (error) {
                  if (error.name != "AbortError") {
                  }
               });
         }
      }

      function createTable() {
         pollTable = new FeatureTable({
            layer: pollLayer,
            multiSortEnabled: false,
            label: "",
            visibleElements: {
               selectionColumn: false,
               menu: false,
               header: false,
               columnMenus: false
            },
            view: view,
            tableTemplate: {
               columnTemplates: [
                  {
                     type: "field",
                     fieldName: "pollingLocationId",
                     label: "ID",
                     visible: false
                  },
                  {
                     type: "field",
                     fieldName: "pollPlace",
                     label: "Location"
                  },
                  {
                     type: "field",
                     fieldName: "waitTime",
                     label: "Wait Time"
                  }
               ]
            },
            container: document.getElementById("tableDiv")
         });

         return pollLayer;
      }

      view.on("pointer-move", (event) => {
         const opts = {
            include: pollLayer
         };

         view.hitTest(event, opts).then((response) => {
            if (response.results.length) {
               const graphic = response.results[0].graphic;

               view.popup.open({
                  location: graphic.geometry.centeroid,
                  features: [graphic]
               });
            } else {
               view.popup.close();
            }
         });
      });

      function waitTimePopup(feature) {
         const attr = feature.graphic.attributes;
         const div = document.createElement("div");
         var content;

         if (attr.waitTime <= 19) {
            content = 'Wait Time: ' + '<span style=\"font-weight:bold;">' + attr.waitTime + '</span>';
         }

         if (attr.waitTime >= 20 && attr.waitTime < 40) {
            content = 'Wait Time: ' + '<span style=\"font-weight:bold;">' + attr.waitTime + '</span>';
         }

         if (attr.waitTime >= 40 && attr.waitTime <= 120) {
            content = 'Wait Time: ' + '<span style=\"font-weight:bold;">' + attr.waitTime + '</span>';
         }

         if (attr.waitTime > 900) {
            content = 'Wait Time: ' + '<span style=\"font-weight:bold;">Closed</span>';
         }

         div.innerHTML = '<div class="wait-time-popup">' + content + '</div><div class="address-popup">' + attr.streetAddress + '<br>' + attr.city + ', ' + attr.zip + '</div>';

         return div;
      }

      function createLegend() {
         var legend = new Legend({
            container: document.createElement("div"),
            view: view
         });

         var expand1 = new Expand({
            expandIconClass: "esri-icon-legend",
            expandTooltip: "Expand Legend",
            view: view,
            content: legend,
            exapnded: false
         });

         view.ui.add(expand1, "top-left");
      }

      function errback(error) {
         console.error(error);

         var noElectionDiv = document.getElementById('noElectionId');
         noElectionDiv.style = "display: block;";

         var noElectionDiv = document.getElementById('maparea');
         noElectionDiv.style = "display: none;";
      }
   });
}