var contentWidth = 960;
var contentHeight = 643;
var content = document.getElementById("player");
var contentContainer = document.getElementById("content");
var contentRestrictor = document.getElementById("left")

function hide(id){
    document.getElementById(id).style.display="none";
}

function show(id){
    document.getElementById(id).style.display="block";
}


function resizeContent(event){
    var targetWidth = contentRestrictor.clientWidth;
    var scale = targetWidth / contentWidth;
    content.style.setProperty("transform","scale("+scale+")");
    contentContainer.style.setProperty("height",contentHeight*scale + "px")
    console.log(contentHeight*scale + "px");
}

resizeContent();
