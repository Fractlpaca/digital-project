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
    var newName = $("#title_input").val();
    console.log(newName);
    $.post(route+"/edit", {title: newName}, function(data, status){
        $("#title").text($("#title_input").val());
        $("title").text($("#title_input").val());
    }).fail(function(xhr){
        if(xhr.readyState==4){
            alert(xhr.responseText);
        }else{
            alert("Could not complete request. Please try again later.")
        }
    });
    show('title_div');
    hide('title_form');
}

function ajaxEditTags(route){
    var newTags = $("#tags_input").val();
    $.post(route+"/edit", {tags: newTags}, function(data, status){
        //alert(data);
        $("#tags").html(data);
    }).fail(function(xhr){
        if(xhr.readyState==4){
            alert(xhr.responseText);
        }else{
            alert("Could not complete request. Please try again later.")
        }
    });
    show('tags_div');
    hide('tags_form');
}

function ajaxEditAuthors(route){
    var newAuthors = $("#authors_input").val();
    $.post(route+"/edit", {authors: newAuthors}, function(data, status){
        //alert(data);
        $("#authors").html(data);
    }).fail(function(xhr){
        if(xhr.readyState==4){
            alert(xhr.responseText);
        }else{
            alert("Could not complete request. Please try again later.")
        }
    });
    show('authors_div');
    hide('authors_form');
}

function ajaxEditDescription(route){
    var newDescription = $("#description_input").val();
    $.post(route+"/edit", {description: newDescription}, function(data, status){
        var newDescription = document.getElementById("description_input").value;
        //alert(newDescription);
        //alert(data);
        $("#description").text(newDescription);
    }).fail(function(xhr){
        if(xhr.readyState==4){
            alert(xhr.responseText);
        }else{
            alert("Could not complete request. Please try again later.")
        }
    });
    show('description_div');
    hide('description_form');
}


function ajaxAddComment(route){
    var newComment = $("#new_comment").val();
    $.post(route+"/comment", {text: newComment}, function(data, status){
        var newDescription = document.getElementById("description_input").value;
        //alert(newDescription);
        $("#comments").prepend(data);
        $("#new_comment").val("");
    }).fail(function(xhr){
        if(xhr.readyState==4){
            alert(xhr.responseText);
        }else{
            alert("Could not complete request. Please try again later.")
        }
    });
}


function ajaxRemoveComment(route, comment_id){
    if(confirm("Permanantly delete comment?")){
        $.post(route+"/deleteComment", {comment_id: comment_id}, function(data, status){
            //alert(newDescription);
            $("#comment_"+String(comment_id)).remove();
            
        }).fail(function(xhr){
            if(xhr.readyState==4){
                alert(xhr.responseText);
            }else{
                alert("Could not complete request. Please try again later.")
            }
        });
    }
}


/*ajaxChangeThumbnail(route){
    var newThumbnail = $("#new_comment").val();
    $.post(route+"/comment", {text: newComment}, function(data, status){
        var newDescription = document.getElementById("description_input").value;
        //alert(newDescription);
        $("#comments").prepend(data);
        $("#new_comment").val("");
    }).fail(function(xhr){
        if(xhr.readyState==4){
            alert(xhr.responseText);
        }else{
            alert("Could not complete request. Please try again later.")
        }
    });
}*/

function ajaxChangeThumbnail(route){
    $.ajax({
        url: $("#thumbnail_form").attr("action"),
        //contentType: "multipart/form-data",
        type: "POST",
        data: new FormData(document.getElementById("thumbnail_form")),
        contentType: false,
        processData: false,
        success: function(data, status, xhr){
            alert(data);
            var date = new Date();
            var now = String(date.getTime());
            $("#thumbnail").attr("src",route+"/thumbnail?time="+now);
        },
        error: function(xhr){
            if(xhr.readyState==4){
                alert(xhr.responseText);
            }else{
                alert("Could not complete request. Please try again later.")
            }
        }
    });
};


resizeContent();
