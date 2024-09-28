function loadScript(url) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = url;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

async function initialize() {
    try {
        // Load scripts
        await loadScript('/static/js/app.js');
        
        // In the future, this will be updated after logic process
        const userEmail = "rahmansahinler1@gmail.com";

        // Fetch initial user data
        const userData = await window.fetchUserData(userEmail);
        if (!userData) {
            throw new Error('Failed to load user data');
        }

        // Load chat elements
        const chatBox = document.querySelector('.chat-box');
        const userInput = document.getElementById('user-input');
        const sendButton = document.querySelector('.btn-send-message');

        // Load file selection elements
        const fileInput = document.getElementById('file-input');
        const selectedFileList = document.querySelector('.selected-file-list');
        const selectFilesButton = document.getElementById('btn-select-files');
        const removeSelectionButton = document.getElementById('btn-remove-selection');
        
        // Load file upload elements
        const domainFileList = document.querySelector('.domain-file-list');
        const uploadFilesButton = document.getElementById('btn-upload-files');
        const removeUploadButton = document.getElementById('btn-remove-upload');
        
        // Initialize functions
        initChat(chatBox, userInput, sendButton, userEmail);
        initselectFiles(selectFilesButton, fileInput, uploadFilesButton, selectedFileList, removeSelectionButton);
        initRemoveSelection(selectedFileList, uploadFilesButton, removeSelectionButton);
        initUploadFiles(uploadFilesButton, userEmail, domainFileList, removeUploadButton, selectedFileList);
        initRemoveUpload(removeUploadButton, uploadFilesButton, domainFileList, userEmail);

        // Update the initial widgets when first loaded
        updateDomainList(userData, domainFileList, removeUploadButton);
        

    } catch (error) {
        console.error('Error initializing app:', error);
    }
}

document.addEventListener('DOMContentLoaded', initialize);