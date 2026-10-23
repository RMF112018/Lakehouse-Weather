'use strict';
const form=document.querySelector('form'),button=document.querySelector('button'),message=document.querySelector('#message');
let csrf='';
async function challenge(){const response=await fetch('api/auth/status',{cache:'no-store'});const data=await response.json();if(!response.ok)throw Error();if(data.authenticated){location.replace('./');return;}csrf=data.csrf;button.disabled=false;message.textContent='';}
form.addEventListener('submit',async event=>{event.preventDefault();button.disabled=true;message.textContent='Signing in…';try{const response=await fetch('api/auth/login',{method:'POST',headers:{'Content-Type':'application/json','X-Weather-CSRF':csrf},body:JSON.stringify({email:form.email.value,password:form.password.value})});form.password.value='';if(response.ok){location.replace('./');return;}await challenge();message.textContent='Unable to sign in. Check your details or try again later.';}catch{message.textContent='Sign-in is unavailable. Please try again later.';}});
challenge().catch(()=>{message.textContent='Sign-in is unavailable. Please try again later.';});
