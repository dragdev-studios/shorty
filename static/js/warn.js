const warningElement = document.createElement("div");
const warningHeader = document.createElement("h3");
const warningBody = document.createElement("p");
const warningCode = document.createElement("code");

warningElement.style.zIndex = "1";
warningElement.hidden = true;
document.body.appendChild(warningElement);

function callback() {
    warningHeader.innerText = null;
    warningBody.innerText = null;
    warningCode.innerText = null;
    warningElement.hidden = true;
};


function updateWarning(head = null, body = null, code = null, reset_after = 120) {
    warningElement.hidden = false;
    if(head!==null) {
        warningHeader.innerText = head;
    };
    if(body!==null) {
        warningBody.innerText = body;
    };
    if(code!==null) {
        warningCode.innerText = code;
        hljs.highlightBlock(warningCode);
    };
    setTimeout(callback, reset_after*1000);
};
