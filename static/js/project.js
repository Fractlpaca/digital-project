var contentWidth = 960;
var contentHeight = 643;
var content = document.getElementById("player");
var contentContainer = document.getElementById("content");
var contentRestrictor = document.getElementById("left")

var OFFLINE_ERROR = "Could not complete request. Please try again later.";

function hide(id){
    document.getElementById(id).style.display="none";
}

function show(id){
    document.getElementById(id).style.display="block";
}


function resizeContent(event){
    //var targetWidth = $("#left").attr("clientWidth");
    var targetWidth = document.getElementById("left").clientWidth;
    var scale = targetWidth / contentWidth;
    //content.style.setProperty("transform","scale("+scale+")");
    $("#player").css("transform","scale("+scale+")");
    //contentContainer.style.setProperty("height",contentHeight*scale + "px");
    $("#content").css("height",contentHeight*scale + "px");
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
            alert(OFFLINE_ERROR)
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
            alert(OFFLINE_ERROR)
        }
    });
    show('tags_div');
    hide('tags_form');
}

function ajaxEditAuthors(route){
    var newAuthors = $("#authors_input").val();
    $.post(route+"/edit", {authors: newAuthors}, function(data, status){
        //alert(data);
        $("#authors").text(data);
    }).fail(function(xhr){
        if(xhr.readyState==4){
            alert(xhr.responseText);
        }else{
            alert(OFFLINE_ERROR)
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
            alert(OFFLINE_ERROR)
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
            alert(OFFLINE_ERROR)
        }
    });
}


function ajaxRemoveComment(route, comment_id){
    if(confirm("Permanantly delete comment?")){
        $.post(route+"/deleteComment", {comment_id: comment_id}, function(data, status){
            $("#comment_"+String(comment_id)).remove();
            
        }).fail(function(xhr){
            if(xhr.readyState==4){
                alert(xhr.responseText);
            }else{
                alert(OFFLINE_ERROR)
            }
        });
    }
}

function ajaxAddAccess(route, form_id){
    $.ajax({
        url: $("#"+form_id).attr("action"),
        //contentType: "multipart/form-data",
        type: "POST",
        data: new FormData(document.getElementById(form_id)),
           contentType: false,
        processData: false,
        success: function(data, status){
            //alert(data);
            var access_id = parseInt(data);
            $("#access_"+String(access_id)).remove();
            var html_data = data.slice(data.indexOf("<"));
            $("#user_access_rows").prepend(html_data);
            $("#access_form_email").val("");
        },
        error: function(xhr){
            if(xhr.readyState==4){
                alert(xhr.responseText);
            }else{
                alert(OFFLINE_ERROR)
            }
        }
    });
}

function ajaxRemoveAccess(route, access_id){
    if(confirm("Unshare?")){
        $.post(route+"/deleteAccess", {access_id: access_id}, function(data, status){
            $("#access_"+String(access_id)).remove();
        }).fail(function(xhr){
            if(xhr.readyState==4){
                alert(xhr.responseText);
            }else{
                alert(OFFLINE_ERROR)
            }
        });
    }
}

function ajaxSimpleShare(route){
    var newSetting = $("#setting").val();
    $.post(route+"/simpleShare", {setting: newSetting}, function(data, status){
        alert(data);
        //alert(newDescription);
        //alert(data);
    }).fail(function(xhr){
        if(xhr.readyState==4){
            alert(xhr.responseText);
        }else{
            alert(OFFLINE_ERROR)
        }
    });
}


function ajaxChangeThumbnail(route){
    $.ajax({
        url: $("#thumbnail_form").attr("action"),
        //contentType: "multipart/form-data",
        type: "POST",
        data: new FormData(document.getElementById("thumbnail_form")),
        contentType: false,
        processData: false,
        success: function(data, status, xhr){
            //alert(data);
            var date = new Date();
            var now = String(date.getTime());
            $("#thumbnail").attr("src",route+"/thumbnail?time="+now);
        },
        error: function(xhr){
            if(xhr.readyState==4){
                alert(xhr.responseText);
            }else{
                alert(OFFLINE_ERROR)
            }
        }
    });
};

function ajaxUploadDownload(route){
    $.ajax({
        url: $("#upload_download_form").attr("action"),
        //contentType: "multipart/form-data",
        type: "POST",
        data: new FormData(document.getElementById("upload_download_form")),
        contentType: false,
        processData: false,
        success: function(data, status, xhr){
            //alert(data);
            $("#downloads").prepend(data);
        },
        error: function(xhr){
            if(xhr.readyState==4){
                alert(xhr.responseText);
            }else{
                alert(OFFLINE_ERROR)
            }
        }
    });
};

function ajaxUploadContent(route){
    $.ajax({
        url: $("#upload_content_form").attr("action"),
        //contentType: "multipart/form-data",
        type: "POST",
        data: new FormData(document.getElementById("upload_content_form")),
        contentType: false,
        processData: false,
        success: function(data, status, xhr){
            //alert(data);
            $("#content").empty();
            $("#content").append(data);
            resizeContent();
        },
        error: function(xhr){
            if(xhr.readyState==4){
                alert(xhr.responseText);
            }else{
                alert(OFFLINE_ERROR)
            }
        }
    });
};

function ajaxRemoveDownload(route, filename){
    if(confirm("Permanantly delete download?")){
        $.post(route+"/deleteDownload", {filename: filename}, function(data, status){
            document.getElementById("download_"+String(filename)).remove();
        }).fail(function(xhr){
            if(xhr.readyState==4){
                alert(xhr.responseText);
            }else{
                alert(OFFLINE_ERROR)
            }
        });
    }
}


resizeContent();
