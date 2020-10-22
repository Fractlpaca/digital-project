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
    contentContainer.style.setProperty("height",contentHeight*scale + "px");
    console.log(contentHeight*scale + "px");
}

function ajaxEditTitle(route){
    var newName = document.getElementById("title_input").value;
    console.log(newName);
    $.post(route+"/edit", {title: newName}, function(data, status){
        if(status=="success"){
            $("#title").text(data);
            $("title").text(data);
        }
    });
    show('title_div');
    hide('title_form');
}

function ajaxEditTags(route){
    var newTags = document.getElementById("tags_input").value;
    $.post(route+"/edit", {tags: newTags}, function(data, status){
        //alert(data);
        if(status=="success"){
            $("#tags").html(data);
        }
    });
    show('tags_div');
    hide('tags_form');
}

function ajaxEditAuthors(route){
    var newAuthors = document.getElementById("authors_input").value;
    $.post(route+"/edit", {authors: newAuthors}, function(data, status){
        //alert(data);
        if(status=="success"){
            $("#authors").html(data);
        }
    });
    show('authors_div');
    hide('authors_form');
}

function ajaxEditDescription(route){
    var newDescription = document.getElementById("description_input").value;
    $.post(route+"/edit", {description: newDescription}, function(data, status){
        var newDescription = document.getElementById("description_input").value;
        //alert(newDescription);
        //alert(data);
        if(status=="success"){
            $("#description").text(newDescription);
        }
    });
    show('description_div');
    hide('description_form');
}


resizeContent();
