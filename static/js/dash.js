function deleteProject(project_id, project_name){
    if(confirm("Are you sure you want to delete project '"+project_name+"'?\nThis action is permanent and cannot be undone.")){
        $.post("/deleteProject",{project_id: project_id},function(){
            location.reload();
        });
    }
}
