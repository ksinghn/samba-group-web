$(function(){
  // connection form
  $('#connect-form').on('submit', function(e){
    e.preventDefault();
    var form = $(this);
    $.post('/set_connection', form.serialize(), function(){
      $('#conn-status').text('Connected (saved)').addClass('text-success');
      setTimeout(()=>$('#conn-status').text(''),3000);
    }).fail(function(xhr){
      $('#conn-status').text('Failed').addClass('text-danger');
    });
  });

  // show connection info
  function refreshConn(){
    $.get('/connection_info', function(data){
      if(data.connected){
        $('#conn-status').text(data.host+"@"+data.username).addClass('text-success');
      }
    });
  }
  refreshConn();

  // Users page
  if($('#users-table').length){
    var table = $('#users-table').DataTable({columns:[{data:'username'},{data:'email'},{data:'groups'}], pageLength:10});
    function loadUsers(){
      $.get('/api/users', function(data){
        if(data.error){alert(data.error);return}
        var rows = data.users.map(u=>({username:u.username, email:u.email, groups:(u.groups||[]).join(', ')}));
        table.clear(); table.rows.add(rows); table.draw();
      }).fail(function(xhr){alert(xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : 'Failed to fetch users')});
    }
    loadUsers();
    $('#create-user-form').on('submit', function(e){
      e.preventDefault();
      var payload = $(this).serializeArray();
      var obj = {};
      payload.forEach(function(p){obj[p.name]=p.value});
      $.ajax({url:'/api/create_user', method:'POST', contentType:'application/json', data:JSON.stringify(obj), success:function(res){
        $('#create-user-output').html('<pre>'+res.stdout+ (res.stderr?('\nERR:\n'+res.stderr):'') +'</pre>');
        loadUsers();
      }, error:function(xhr){$('#create-user-output').text(xhr.responseJSON && xhr.responseJSON.error? xhr.responseJSON.error : 'Error')} });
    });
  }

  // Groups page
  if($('#groups-table').length){
    var gtable = $('#groups-table').DataTable({columns:[{data:'name'},{data:'description'}], pageLength:10});
    function loadGroups(){
      $.get('/api/groups', function(data){
        if(data.error){alert(data.error);return}
        gtable.clear(); gtable.rows.add(data.groups); gtable.draw();
        // populate group-select if present
        var sel = $('#group-select');
        if(sel.length){
          sel.empty(); data.groups.forEach(g=>sel.append($('<option>').attr('value',g.name).text(g.name)));
          sel.trigger('change');
        }
      }).fail(function(xhr){alert(xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : 'Failed to fetch groups')});
    }
    loadGroups();
    $('#create-group-form').on('submit', function(e){
      e.preventDefault();
      var obj = {};
      $(this).serializeArray().forEach(function(p){obj[p.name]=p.value});
      $.ajax({url:'/api/create_group', method:'POST', contentType:'application/json', data:JSON.stringify(obj), success:function(res){
        $('#create-group-output').html('<pre>'+res.stdout+(res.stderr?('\nERR:\n'+res.stderr):'')+'</pre>');
        loadGroups();
      }, error:function(xhr){$('#create-group-output').text(xhr.responseJSON && xhr.responseJSON.error? xhr.responseJSON.error : 'Error')} });
    });
  }

  // Group members page
  if($('#group-select').length){
    function loadGroupsIntoSelect(){
      $.get('/api/groups', function(data){
        var sel = $('#group-select'); sel.empty(); data.groups.forEach(g=>sel.append($('<option>').val(g.name).text(g.name)));
        sel.trigger('change');
      });
    }
    loadGroupsIntoSelect();
    function loadMembers(group){
      $.get('/api/group_members', {group:group}, function(data){
        if(data.error){alert(data.error);return}
        var memT = $('#members-table tbody'); memT.empty(); data.members.forEach(u=>memT.append('<tr><td><input type="checkbox" name="members" value="'+u+'"></td><td>'+u+'</td></tr>'));
        var nonT = $('#nonmembers-table tbody'); nonT.empty(); data.non_members.forEach(u=>nonT.append('<tr><td><input type="checkbox" name="nonmembers" value="'+u+'"></td><td>'+u+'</td></tr>'));
      }).fail(function(xhr){alert(xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : 'Failed to fetch group members')});
    }
    $('#group-select').on('change', function(){ loadMembers($(this).val()); });

    $('#add-members-form').on('submit', function(e){
      e.preventDefault();
      var group = $('#group-select').val();
      var users = [];
      $('#nonmembers-table input[name="nonmembers"]:checked').each(function(){users.push($(this).val())});
      if(users.length==0){alert('Select users to add'); return}
      $.ajax({url:'/api/add_members', method:'POST', contentType:'application/json', data:JSON.stringify({group:group, users:users}), success:function(res){
        $('#group-members-output').html('<pre>'+res.stdout+(res.stderr?('\nERR:\n'+res.stderr):'')+'</pre>');
        loadMembers(group);
      }, error:function(xhr){$('#group-members-output').text(xhr.responseJSON && xhr.responseJSON.error? xhr.responseJSON.error : 'Error')} });
    });

    $('#remove-members-form').on('submit', function(e){
      e.preventDefault();
      var group = $('#group-select').val();
      var users = [];
      $('#members-table input[name="members"]:checked').each(function(){users.push($(this).val())});
      if(users.length==0){alert('Select users to remove'); return}
      $.ajax({url:'/api/remove_members', method:'POST', contentType:'application/json', data:JSON.stringify({group:group, users:users}), success:function(res){
        $('#group-members-output').html('<pre>'+res.stdout+(res.stderr?('\nERR:\n'+res.stderr):'')+'</pre>');
        loadMembers(group);
      }, error:function(xhr){$('#group-members-output').text(xhr.responseJSON && xhr.responseJSON.error? xhr.responseJSON.error : 'Error')} });
    });
  }
});
