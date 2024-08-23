import Plotly from 'plotly.js-dist'
var plots = new Array(8);
var plots_data = new Array(8);
var plots_layout = new Array(8);
const NUM_PLOT = 8

const socket = new WebSocket("ws://localhost:60080/");
socket.addEventListener("message", (event) => {
    //console.log("Message from server ", event.data);
    const json = JSON.parse(event.data)
    console.log(json)
    
    xy = [{x:"time", y:"ai_phy_0"}, {x:"time", y:"ai_phy_1"}, {x:"time", y:"ai_phy_2"}, {x:"time", y:"ai_phy_3"}, {x:"time", y:"ai_phy_4"}, {x:"time", y:"ai_phy_5"}, {x:"time", y:"ai_phy_6"}, {x:"time", y:"ai_phy_7"}]

    for (var num = 0; num < NUM_PLOT; num++) {
        // if (plots_data[num][0].x.length == 0) {
        //     plots_data[num][0].x = [json.data[0][xy[num].x]]
        //     plots_data[num][0].y = [json.data[0][xy[num].y]]
        // } else {
            
        // }
        plots_data[num][0].x.push(json.data[0][xy[num].x])
        plots_data[num][0].y.push(json.data[0][xy[num].y])
        plots_layout[num].title = xy[num].x+ " - "+ xy[num].y
        plots_layout[num].xaxis = {title: json.label[xy[num].x]+"["+json.unit[xy[num].x]+"]"}
        plots_layout[num].yaxis = {title: json.label[xy[num].y]+"["+json.unit[xy[num].y]+"]"}
        Plotly.redraw(document.getElementById('plot_' + String(num)));
    }
});

async function main_function() {
    for (var num = 0; num < NUM_PLOT; num++) {
        plots_data[num] = [{
            x: [],
            y: [],
            type: 'scattergl'
        }]
        plots_layout[num] = { 
            title: '',
            font: {size: 18},
            margin: {r: 10},
        };
        var _config = {responsive: true}
        var _target = 'plot_' + String(num);
        var _plot_pos = document.getElementById(_target);
        plots[num] = Plotly.newPlot(_plot_pos, plots_data[num], plots_layout[num], _config);
    }
}
main_function();

async function test_function() {
    const RATIO = 10
    const OFFSET = 3.14159/4
    var var_x = [];
    var var_y = new Array(8);

    for (var num = 0; num < NUM_PLOT; num++) {
        var_y[num] = new Array(1000);
    }
    
    for (di = 0; di < 1000; di++) {
        var_x[di] = di;
        for (var num = 0; num < NUM_PLOT; num++) {
            var_y[num][di] = 1000*Math.sin(di/1000*RATIO+num*OFFSET);
        }
    }
    
    for (var num = 0; num < NUM_PLOT; num++) {
        var _data = {
            x: var_x,
            y: var_y[num],
            type: 'scattergl'
        }
        var _layout = { 
            title: 'Chart ' + String(num),
            font: {size: 18},
            margin: {r: 10},
        };
        var _config = {responsive: true}
        var _target = 'plot_' + String(num);
        var _plot_pos = document.getElementById(_target);
        plots[num] = Plotly.newPlot(_plot_pos, [_data], _layout, _config);
    }
}
//test_function();






