// Core Event System
class EventEmitter {
    constructor() {
        this.events = {};
    }

    on(event, callback) {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(callback);
    }

    emit(event, data) {
        if (!this.events[event]) return;
        this.events[event].forEach(callback => callback(data));
    }
}

// Base Component
class Component {
    constructor(element) {
        this.element = element;
        this.events = new EventEmitter();
    }

    createElement(tag, className = '') {
        const element = document.createElement(tag);
        if (className) element.className = className;
        return element;
    }

    destroy() {
        this.element.remove();
    }
}

// Domain Card Component
class DomainCard extends Component {
    constructor(domainData) {
        const element = document.createElement('div');
        element.className = 'domain-card';
        super(element);
        
        this.data = domainData;
        this.render();
        this.attachEventListeners();
    }

    render() {
        this.element.innerHTML = `
            <div class="domain-content">
                <div class="checkbox-wrapper">
                    <input type="checkbox" id="${this.data.id}" class="domain-checkbox">
                    <label for="${this.data.id}" class="checkbox-label"></label>
                </div>
                <div class="domain-info">
                    <h6 title="${this.data.name}">${this.data.name}</h6>
                    <span class="file-count">${this.data.fileCount || 0} files</span>
                </div>
            </div>
        `;
    }

    attachEventListeners() {
        const checkbox = this.element.querySelector('.domain-checkbox');
        checkbox.addEventListener('change', () => {
            this.events.emit('selected', {
                id: this.data.id,
                selected: checkbox.checked
            });
        });
    }

    setSelected(selected) {
        const checkbox = this.element.querySelector('.domain-checkbox');
        checkbox.checked = selected;
    }
}

// Domain Manager (Storage)
class DomainManager {
    constructor() {
        this.domains = new Map();
        this.selectedDomainId = null;
        this.events = new EventEmitter();
    }

    addDomain(domain) {
        const domainCard = new DomainCard(domain);
        this.domains.set(domain.id, {
            data: domain,
            component: domainCard
        });

        domainCard.events.on('selected', ({id, selected}) => {
            if (selected) {
                this.selectDomain(id);
            }
        });

        return domainCard;
    }

    selectDomain(domainId) {
        // Deselect previous
        if (this.selectedDomainId) {
            const previous = this.domains.get(this.selectedDomainId);
            if (previous) {
                previous.component.setSelected(false);
            }
        }

        // Select new
        const domain = this.domains.get(domainId);
        if (domain) {
            domain.component.setSelected(true);
            this.selectedDomainId = domainId;
            this.events.emit('domainSelected', domain.data);
        }
    }
}

class DomainSettingsModal extends Component {
    constructor() {
        const element = document.createElement('div');
        element.id = 'domainSelectModal';
        element.className = 'modal fade';
        element.setAttribute('tabindex', '-1');
        element.setAttribute('aria-hidden', 'true');
        super(element);
        
        this.render();
        this.setupEventListeners();
    }

    render() {
        this.element.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="domain-modal-wrapper">
                        <div class="domain-header">
                            <h5>Select Domain</h5>
                            <button type="button" class="close-button" data-bs-dismiss="modal">
                                <i class="bi bi-x"></i>
                            </button>
                        </div>

                        <div class="domain-search">
                            <i class="bi bi-search"></i>
                            <input type="text" placeholder="Search domains..." class="domain-search-input" id="domainSearchInput">
                        </div>

                        <div class="domains-container" id="domainsContainer">
                            <!-- Domains will be populated here -->
                        </div>

                        <button class="new-domain-button" id="newDomainBtn">
                            <i class="bi bi-plus-circle"></i>
                            Create New Domain
                        </button>

                        <button class="select-button">
                            Select Domain
                        </button>
                    </div>
                </div>
            </div>

            <!-- Delete Confirmation Modal -->
            <div class="modal fade" id="deleteConfirmModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered modal-sm">
                    <div class="modal-content">
                        <div class="domain-modal-wrapper text-center">
                            <h6 class="mb-3">Delete Domain?</h6>
                            <p class="text-secondary mb-4">Are you sure you want to delete this domain?</p>
                            <div class="d-flex gap-3">
                                <button class="btn btn-outline-secondary flex-grow-1" data-bs-dismiss="modal">Cancel</button>
                                <button class="btn btn-danger flex-grow-1" id="confirmDeleteBtn">Delete</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Template for new domain input -->
            <template id="newDomainInputTemplate">
                <div class="domain-card new-domain-input-card">
                    <input type="text" class="new-domain-input" placeholder="Enter domain name" autofocus>
                    <div class="new-domain-actions">
                        <button class="confirm-button"><i class="bi bi-check"></i></button>
                        <button class="cancel-button"><i class="bi bi-x"></i></button>
                    </div>
                </div>
            </template>
        `;

        document.body.appendChild(this.element);
    }

    setupEventListeners() {
        // Search functionality
        const searchInput = this.element.querySelector('#domainSearchInput');
        searchInput?.addEventListener('input', (e) => {
            this.events.emit('domainSearch', e.target.value);
        });

        // New domain button
        const newDomainBtn = this.element.querySelector('#newDomainBtn');
        newDomainBtn?.addEventListener('click', () => {
            this.handleNewDomain();
        });

        // Select button
        const selectButton = this.element.querySelector('.select-button');
        selectButton?.addEventListener('click', () => {
            const selectedCheckbox = this.element.querySelector('.domain-checkbox:checked');
            if (selectedCheckbox) {
                const domainCard = selectedCheckbox.closest('.domain-card');
                this.events.emit('domainSelected', domainCard.dataset.domainId);
                this.hide();
            }
        });

        // Delete confirmation
        const confirmDeleteBtn = this.element.querySelector('#confirmDeleteBtn');
        confirmDeleteBtn?.addEventListener('click', () => {
            this.events.emit('domainDelete', this.domainToDelete);
            this.hideDomainDeleteModal();
        });
    }

    handleNewDomain() {
        const template = document.getElementById('newDomainInputTemplate');
        const domainsContainer = this.element.querySelector('#domainsContainer');
        
        if (template && domainsContainer) {
            const clone = template.content.cloneNode(true);
            domainsContainer.appendChild(clone);

            const inputCard = domainsContainer.querySelector('.new-domain-input-card');
            const input = inputCard.querySelector('.new-domain-input');
            
            this.setupNewDomainHandlers(inputCard, input);
            input.focus();
        }
    }

    setupNewDomainHandlers(inputCard, input) {
        const confirmBtn = inputCard.querySelector('.confirm-button');
        const cancelBtn = inputCard.querySelector('.cancel-button');

        const handleConfirm = () => {
            const name = input.value.trim();
            if (name) {
                this.events.emit('domainCreate', name);
                inputCard.remove();
            }
        };

        confirmBtn.addEventListener('click', handleConfirm);
        cancelBtn.addEventListener('click', () => inputCard.remove());
        
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleConfirm();
        });
        
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') inputCard.remove();
        });
    }

    updateDomainsList(domains) {
        const container = this.element.querySelector('#domainsContainer');
        if (container) {
            container.innerHTML = domains.map(domain => this.createDomainCard(domain)).join('');
            this.setupDomainCardListeners();
        }
    }

    createDomainCard(domain) {
        return `
            <div class="domain-card" data-domain-id="${domain.id}">
                <div class="domain-content">
                    <div class="checkbox-wrapper">
                        <input type="checkbox" id="${domain.id}" class="domain-checkbox">
                        <label for="${domain.id}" class="checkbox-label"></label>
                    </div>
                    <div class="domain-info">
                        <h6 title="${domain.name}">${domain.name}</h6>
                        <span class="file-count">${domain.fileCount} files</span>
                    </div>
                </div>
                <div class="domain-actions">
                    <button class="edit-button">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="delete-button">
                        <i class="bi bi-trash3"></i>
                    </button>
                </div>
            </div>
        `;
    }

    setupDomainCardListeners() {
        // Add event listeners for domain cards
        this.element.querySelectorAll('.domain-card').forEach(card => {
            // Delete button
            card.querySelector('.delete-button')?.addEventListener('click', (e) => {
                e.stopPropagation();
                this.domainToDelete = card.dataset.domainId;
                this.showDomainDeleteModal();
            });

            // Edit button
            card.querySelector('.edit-button')?.addEventListener('click', (e) => {
                e.stopPropagation();
                this.enableDomainEditing(card);
            });
        });
    }

    show() {
        const modal = new bootstrap.Modal(this.element);
        modal.show();
    }

    hide() {
        const modal = bootstrap.Modal.getInstance(this.element);
        if (modal) {
            modal.hide();
        }
    }

    showDomainDeleteModal() {
        const modal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
        modal.show();
    }

    hideDomainDeleteModal() {
        const modal = bootstrap.Modal.getInstance(document.getElementById('deleteConfirmModal'));
        if (modal) {
            modal.hide();
        }
    }
}

class FileUploadModal extends Component {
    constructor() {
        const element = document.createElement('div');
        element.id = 'fileUploadModal';
        element.className = 'modal fade';
        element.setAttribute('tabindex', '-1');
        element.setAttribute('aria-hidden', 'true');
        super(element);
        
        this.isUploading = false;
        this.uploadedFiles = new Set();
        this.uploadedFileObjects = new Map();
        
        this.render();
        this.setupEventListeners();
    }

    render() {
        this.element.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="domain-modal-wrapper">
                        <div class="modal-header border-0 d-flex align-items-center">
                            <div>
                                <h6 class="mb-0">Selected Domain: <span class="domain-name text-primary-green text-truncate"></span></h6>
                            </div>
                            <button type="button" class="close-button" data-bs-dismiss="modal">
                                <i class="bi bi-x"></i>
                            </button>
                        </div>

                        <div class="upload-container">
                            <div id="fileList" class="file-list mb-3"></div>

                            <div class="upload-area" id="dropZone">
                                <div class="upload-content text-center">
                                    <div class="upload-icon-wrapper">
                                        <div class="upload-icon">
                                            <i class="bi bi-cloud-upload text-primary-green"></i>
                                        </div>
                                    </div>
                                    <h5 class="mb-2">Upload Files</h5>
                                    <p class="mb-3">Drag & drop or <span class="text-primary-green choose-text">choose files</span> to upload</p>
                                    <small class="text-secondary">Supported file types: PDF, DOCX and TXT</small>
                                    <input type="file" id="fileInput" multiple accept=".pdf,.docx,.txt" class="d-none">
                                </div>
                            </div>

                            <button class="upload-btn mt-3" id="uploadBtn" disabled>
                                Upload
                                <div class="upload-progress">
                                    <div class="progress-bar"></div>
                                </div>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(this.element);
    }

    setupEventListeners() {
        const dropZone = this.element.querySelector('#dropZone');
        const fileInput = this.element.querySelector('#fileInput');
        const uploadBtn = this.element.querySelector('#uploadBtn');
        const chooseText = this.element.querySelector('.choose-text');

        // Drag and drop handlers
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                if (!this.isUploading) {
                    dropZone.classList.add('dragover');
                }
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.remove('dragover');
            });
        });

        // File drop handler
        dropZone.addEventListener('drop', (e) => {
            if (!this.isUploading) {
                const files = e.dataTransfer.files;
                this.handleFiles(files);
            }
        });

        // File input handler
        chooseText.addEventListener('click', () => {
            if (!this.isUploading) {
                fileInput.click();
            }
        });

        fileInput.addEventListener('change', () => {
            this.handleFiles(fileInput.files);
        });

        // Upload button handler
        uploadBtn.addEventListener('click', () => {
            this.startUpload();
        });
    }

    handleFiles(newFiles) {
        if (this.isUploading) return;

        const fileList = this.element.querySelector('#fileList');
        const uploadBtn = this.element.querySelector('#uploadBtn');
        const uploadArea = this.element.querySelector('#dropZone');
        let duplicateFound = false;

        Array.from(newFiles).forEach(file => {
            if (this.uploadedFiles.has(file.name)) {
                duplicateFound = true;
                return;
            }

            this.uploadedFileObjects.set(file.name, file);
            this.uploadedFiles.add(file.name);
            this.displayFileInList(file, fileList);
        });

        if (duplicateFound) {
            this.events.emit('warning', 'Some files were skipped as they were already added');
        }

        this.updateUploadUI(fileList, uploadBtn, uploadArea);
    }

    displayFileInList(file, fileList) {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item pending-upload';
        fileItem.dataset.fileName = file.name;
        
        const icon = this.getFileIcon(file.name);
        fileItem.innerHTML = `
            <div class="file-icon">
                <i class="bi ${icon} text-primary-green"></i>
            </div>
            <div class="file-info">
                <div class="file-name">${file.name}</div>
                <div class="file-progress">
                    <div class="progress-bar"></div>
                </div>
            </div>
            <div class="file-remove">
                <i class="bi bi-trash"></i>
            </div>
        `;

        const removeButton = fileItem.querySelector('.file-remove');
        removeButton.addEventListener('click', () => {
            if (!this.isUploading) {
                this.uploadedFiles.delete(file.name);
                this.uploadedFileObjects.delete(file.name);
                fileItem.remove();
                this.updateUploadUI(
                    fileList,
                    this.element.querySelector('#uploadBtn'),
                    this.element.querySelector('#dropZone')
                );
            }
        });

        fileList.appendChild(fileItem);
    }

    getFileIcon(fileName) {
        const extension = fileName.split('.').pop().toLowerCase();
        const iconMap = {
            pdf: 'bi-file-pdf',
            docx: 'bi-file-word',
            doc: 'bi-file-word',
            txt: 'bi-file-text'
        };
        return iconMap[extension] || 'bi-file';
    }

    updateUploadUI(fileList, uploadBtn, uploadArea) {
        if (this.uploadedFiles.size > 0) {
            uploadArea.style.display = 'none';
            uploadBtn.disabled = false;
            this.ensureAddMoreFilesButton(fileList);
        } else {
            uploadArea.style.display = 'flex';
            uploadBtn.disabled = true;
            this.removeAddMoreFilesButton();
        }
    }

    ensureAddMoreFilesButton(fileList) {
        let addFileBtn = this.element.querySelector('.add-file-btn');
        if (!addFileBtn) {
            addFileBtn = document.createElement('button');
            addFileBtn.className = 'add-file-btn';
            addFileBtn.innerHTML = `
                <i class="bi bi-plus-circle"></i>
                Add More Files
            `;
            addFileBtn.addEventListener('click', () => {
                if (!this.isUploading) {
                    this.element.querySelector('#fileInput').click();
                }
            });
            fileList.after(addFileBtn);
        }
        addFileBtn.disabled = this.isUploading;
        addFileBtn.style.opacity = this.isUploading ? '0.5' : '1';
    }

    removeAddMoreFilesButton() {
        const addFileBtn = this.element.querySelector('.add-file-btn');
        if (addFileBtn) {
            addFileBtn.remove();
        }
    }

    startUpload() {
        if (this.uploadedFiles.size === 0 || this.isUploading) return;

        this.isUploading = true;
        const fileItems = this.element.querySelectorAll('.file-item');
        let completed = 0;

        // Disable UI elements
        this.element.querySelector('#uploadBtn').disabled = true;
        const addMoreFilesBtn = this.element.querySelector('.add-file-btn');
        if (addMoreFilesBtn) {
            addMoreFilesBtn.disabled = true;
            addMoreFilesBtn.style.opacity = '0.5';
        }

        fileItems.forEach(item => {
            item.classList.remove('pending-upload');
            item.classList.add('uploading');

            const progressBar = item.querySelector('.progress-bar');
            const progressContainer = item.querySelector('.file-progress');
            progressContainer.style.display = 'block';

            this.simulateFileUpload(item, progressBar, () => {
                completed++;
                item.classList.remove('uploading');
                item.classList.add('uploaded');

                if (completed === fileItems.length) {
                    this.finishUpload();
                }
            });
        });
    }

    simulateFileUpload(fileItem, progressBar, onComplete) {
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 30;
            if (progress >= 100) {
                progress = 100;
                clearInterval(interval);
                onComplete();
            }
            progressBar.style.width = `${progress}%`;
        }, 500);
    }

    finishUpload() {
        this.isUploading = false;
        const filesToAdd = Array.from(this.uploadedFileObjects.values());
        
        // Emit event for parent components
        this.events.emit('filesUploaded', filesToAdd);

        this.uploadedFiles.clear();
        this.uploadedFileObjects.clear();

        setTimeout(() => this.hide(), 500);
    }

    show(domainName = '') {
        const domainNameElement = this.element.querySelector('.domain-name');
        if (domainNameElement) {
            domainNameElement.textContent = domainName;
        }
        const modal = new bootstrap.Modal(this.element);
        modal.show();
    }

    hide() {
        const modal = bootstrap.Modal.getInstance(this.element);
        if (modal) {
            modal.hide();
        }
    }
}

// Sidebar Component
class Sidebar extends Component {
    constructor() {
        const element = document.createElement('div');
        element.className = 'sidebar-container';
        super(element);
        
        this.isOpen = false;
        this.timeout = null;
        this.render();
        this.setupEventListeners();
    }

    render() {
        this.element.innerHTML = `
            <div class="sidebar d-flex flex-column flex-shrink-0 h-100">
                <div class="top-header py-3 px-4">
                    <div class="d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center gap-3">
                            <h1 class="logo-text m-0 d-xl-block">ragchat</h1>
                        </div>
                    </div>
                </div>
                <div class="px-4 py-3">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="d-flex align-items-center gap-2">
                            <i class="bi bi-folder empty-folder"></i>
                            <span class="d-xl-block selected-domain-text">Select Domain</span>
                        </div>
                        <i class="bi bi-gear settings-icon"></i>
                    </div>

                    <div class="file-list-container">
                        <div id="sidebarFileList" class="sidebar-files">
                        </div>
                    </div>
                    <div class="file-add">
                        <button class="open-file-btn">
                            Open File Menu
                        </button>
                        <p class="helper-text">
                            Select your domain and start adding files with file menu
                        </p>
                    </div>
                </div>

                <div class="bottom-section mt-auto">
                    <div class="text-center mb-3">
                        <span class="plan-badge d-xl-block">Free Plan</span>
                    </div>
                    <div class="user-section d-flex align-items-center gap-3 mb-3" role="button" id="userProfileMenu">
                        <div class="user-avatar">i</div>
                        <div class="user-info d-xl-block">
                            <div class="user-email">ibrahimyasing@gmail.com</div>
                            <div class="user-status">
                                <span class="status-dot"></span>
                                Active
                            </div>
                        </div>
                        <div class="user-menu">
                            <div class="menu-item">
                                <i class="bi bi-person-circle"></i>
                                Profile
                            </div>
                            <div class="menu-item">
                                <i class="bi bi-gear"></i>
                                Settings
                            </div>
                            <div class="menu-divider"></div>
                            <div class="menu-item logout-item">
                                <i class="bi bi-box-arrow-right"></i>
                                Logout
                            </div>
                        </div>
                    </div>
                    <div class="bottom-links justify-content-center">
                        <a href="#" class="premium-link">Go Premium!</a>
                        <a href="#">Feedback</a>
                    </div>
                </div>
                <div id="sidebar-seperator"></div>
            </div>
        `;

        // Create backdrop
        this.backdrop = document.createElement('div');
        this.backdrop.className = 'sidebar-backdrop';
        document.body.appendChild(this.backdrop);
    }

    setupEventListeners() {
        // Existing event listeners
        const settingsIcon = this.element.querySelector('.settings-icon');
        settingsIcon.addEventListener('click', () => {
            this.events.emit('settingsClick');
        });
    
        const fileMenuBtn = this.element.querySelector('.open-file-btn');
        fileMenuBtn.addEventListener('click', () => {
            this.events.emit('fileMenuClick');
        });
    
        this.backdrop.addEventListener('click', () => {
            this.toggle(false);
        });
    
        // Add hover handlers for desktop
        if (window.innerWidth >= 992) {
            // Menu trigger hover
            const menuTrigger = document.querySelector('.menu-trigger');
            if (menuTrigger) {
                menuTrigger.addEventListener('mouseenter', () => {
                    console.log('Menu trigger hover');
                    clearTimeout(this.timeout);
                    this.toggle(true);
                });
    
                menuTrigger.addEventListener('mouseleave', () => {
                    this.timeout = setTimeout(() => {
                        if (!this.element.matches(':hover')) {
                            this.toggle(false);
                        }
                    }, 300);
                });
            }
    
            // Sidebar hover
            this.element.addEventListener('mouseenter', () => {
                console.log('Sidebar hover');
                clearTimeout(this.timeout);
                this.toggle(true);
            });
    
            this.element.addEventListener('mouseleave', () => {
                this.timeout = setTimeout(() => {
                    if (!document.querySelector('.menu-trigger')?.matches(':hover')) {
                        this.toggle(false);
                    }
                }, 300);
            });
        }
    
        // Mobile menu trigger handler
        this.events.on('menuTrigger', () => {
            if (window.innerWidth < 992) {
                const menuIcon = document.querySelector('.menu-trigger .bi-list');
                if (menuIcon) {
                    menuIcon.style.transform = this.isOpen ? 'rotate(0)' : 'rotate(45deg)';
                }
                this.toggle();
            }
        });
    
        // Handle window resize
        window.addEventListener('resize', () => {
            if (window.innerWidth >= 992) {
                this.backdrop.classList.remove('show');
                document.body.style.overflow = '';
                const menuIcon = document.querySelector('.menu-trigger .bi-list');
                if (menuIcon) {
                    menuIcon.style.transform = 'rotate(0)';
                }
            }
        });

        // User Profile Menu
        const userSection = this.element.querySelector('#userProfileMenu');
        if (userSection) {
            userSection.addEventListener('click', (e) => {
                e.stopPropagation();
                userSection.classList.toggle('active');
            });

            // Close menu when clicking outside
            document.addEventListener('click', (e) => {
                if (!userSection.contains(e.target)) {
                    userSection.classList.remove('active');
                }
            });

            // Handle menu items
            userSection.querySelectorAll('.menu-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (item.classList.contains('logout-item')) {
                        // Handle logout logic here
                        console.log('Logging out...');
                    }
                    userSection.classList.remove('active');
                });
            });
        }

        // Premium and Feedback links
        const premiumLink = this.element.querySelector('.premium-link');
        if (premiumLink) {
            premiumLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.events.emit('premiumClick');
            });
        }

        const feedbackLink = this.element.querySelector('.bottom-links a:not(.premium-link)');
        if (feedbackLink) {
            feedbackLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.events.emit('feedbackClick');
            });
        }
    }

    toggle(force = null) {
        this.isOpen = force !== null ? force : !this.isOpen;
        this.element.classList.toggle('open', this.isOpen);
        this.backdrop.classList.toggle('show', this.isOpen);
        document.body.style.overflow = this.isOpen ? 'hidden' : '';
    }

    updateDomainSelection(domain) {
        const domainText = this.element.querySelector('.selected-domain-text');
        const folderIcon = this.element.querySelector('.bi-folder');
        
        if (domain) {
            domainText.textContent = domain.name;
            domainText.title = domain.name;
            folderIcon.classList.remove('empty-folder');
        } else {
            domainText.textContent = 'Select Domain';
            domainText.removeAttribute('title');
            folderIcon.classList.add('empty-folder');
        }
    }

    updateFileList(files = []) {
        const fileList = this.element.querySelector('#sidebarFileList');
        fileList.innerHTML = '';
        
        files.forEach(file => {
            // Add file to sidebar list
            const fileItem = this.createFileListItem(file);
            fileList.appendChild(fileItem);
        });

        this.updateFileMenuVisibility();
    }

    createFileListItem(file) {
        const fileItem = document.createElement('li');
        // File item HTML structure...
        return fileItem;
    }

    updateFileMenuVisibility() {
        const fileList = this.element.querySelector('#sidebarFileList');
        const helperText = this.element.querySelector('.helper-text');
        const fileMenuBtn = this.element.querySelector('.open-file-btn');
        const fileListContainer = this.element.querySelector('.file-list-container');

        if (fileList.children.length > 0) {
            helperText.style.display = 'none';
            helperText.style.height = '0';
            helperText.style.margin = '0';
            helperText.style.padding = '0';
        } else {
            fileListContainer.style.height = 'auto';
            fileMenuBtn.style.position = 'static';
            fileMenuBtn.style.width = '100%';
        }
    }

    
}

// Feedback Modal Component
class FeedbackModal extends Component {
    constructor() {
        const element = document.createElement('div');
        element.id = 'feedback-modal';
        element.className = 'feedback-modal';
        super(element);
        
        this.render();
        this.setupEventListeners();
    }

    render() {
        this.element.innerHTML = `
            <div class="feedback-modal-content">
                <div class="feedback-modal-header">
                    <h3>Send Feedback</h3>
                    <button class="close-modal">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="feedback-modal-description">
                    <p>Your feedback really helps us get better!</p>
                    <p>Please follow these steps:</p>
                    <ol>
                        <li>Select the type of your feedback</li>
                        <li>Add your description</li>
                        <li>If it helps explain better, attach a screenshot</li>
                    </ol>
                </div>
                <div class="feedback-modal-body">
                    <form id="feedback-form" enctype="multipart/form-data">
                        <div class="form-group">
                            <label for="feedback-type">Type</label>
                            <select id="feedback-type" name="feedback_type" class="form-control">
                                <option value="general">General Feedback</option>
                                <option value="bug">Bug Report</option>
                                <option value="feature">Feature Request</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="feedback-description">Description</label>
                            <textarea 
                                id="feedback-description"
                                name="feedback_description"
                                class="form-control" 
                                rows="4" 
                                placeholder="Please describe your feedback or issue..."
                            ></textarea>
                        </div>
                        <div class="form-group">
                            <label for="feedback-screenshot">Screenshot (Optional)</label>
                            <input 
                                type="file" 
                                id="feedback-screenshot"
                                name="feedback_screenshot"
                                class="form-control" 
                                accept="image/*"
                            >
                            <small class="form-text">Max size: 2MB</small>
                        </div>
                        <div class="feedback-modal-footer">
                            <button type="button" class="btn-cancel close-modal">Cancel</button>
                            <button type="submit" class="btn-submit">Submit Feedback</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        document.body.appendChild(this.element);
    }

    setupEventListeners() {
        // DOM Event Handlers
        const closeButtons = this.element.querySelectorAll('.close-modal');
        closeButtons.forEach(button => {
            button.addEventListener('click', () => this.hide());
        });
    
        this.element.addEventListener('click', (e) => {
            if (e.target === this.element) {
                this.hide();
            }
        });
    
        const form = this.element.querySelector('#feedback-form');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleSubmit(e);
        });
    
        const screenshotInput = this.element.querySelector('#feedback-screenshot');
        screenshotInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file && file.size > 2 * 1024 * 1024) {
                alert('File size must be less than 2MB');
                e.target.value = '';
            }
        });
    }

    async handleSubmit(e) {
        const form = e.target;
        const submitButton = form.querySelector('.btn-submit');
        submitButton.disabled = true;

        try {
            const formData = new FormData(form);
            const userID = 'current-user-id'; // This should come from app state

            const response = await fetch(`/api/v1/db/insert_feedback?userID=${encodeURIComponent(userID)}`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Failed to submit feedback');
            }

            this.hide();
            // Emit success event for parent components to handle
            this.events.emit('feedbackSubmitted', 'Thank you for your feedback!');

        } catch (error) {
            console.error('Error submitting feedback:', error);
            this.events.emit('feedbackError', 'Failed to submit feedback. Please try again.');
        } finally {
            submitButton.disabled = false;
            form.reset();
        }
    }

    show() {
        this.element.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    hide() {
        this.element.classList.remove('show');
        document.body.style.overflow = '';
        // Reset form
        this.element.querySelector('#feedback-form').reset();
    }
}

// Application
class App {
    constructor() {
        this.domainManager = new DomainManager();
        this.sidebar = new Sidebar();
        this.feedbackModal = new FeedbackModal();
        this.domainSettingsModal = new DomainSettingsModal();
        this.fileUploadModal = new FileUploadModal();
        this.events = new EventEmitter();
        
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Domain related events
        this.domainManager.events.on('domainSelected', (domain) => {
            this.sidebar.updateDomainSelection(domain);
            const files = []; // Get files for selected domain
            this.sidebar.updateFileList(files);
        });

        // Sidebar events
        this.sidebar.events.on('settingsClick', () => {
            this.domainSettingsModal.show();
        });

        this.sidebar.events.on('fileMenuClick', () => {
            const selectedDomain = this.domainManager.getSelectedDomain();
            if (!selectedDomain) {
                this.events.emit('warning', 'Please select a domain first');
                return;
            }
            this.fileUploadModal.show(selectedDomain.data.name);
        });

        this.sidebar.events.on('feedbackClick', () => {
            this.feedbackModal.show();
        });

        // Domain Settings Modal events
        this.domainSettingsModal.events.on('domainCreate', (name) => {
            const newDomain = {
                id: crypto.randomUUID(),
                name: name,
                fileCount: 0
            };
            this.domainManager.addDomain(newDomain);
            this.domainSettingsModal.updateDomainsList(this.domainManager.getAllDomains());
        });

        this.domainSettingsModal.events.on('domainDelete', (domainId) => {
            this.domainManager.deleteDomain(domainId);
            this.domainSettingsModal.updateDomainsList(this.domainManager.getAllDomains());
        });

        this.domainSettingsModal.events.on('domainSearch', (searchTerm) => {
            const filteredDomains = this.domainManager.searchDomains(searchTerm);
            this.domainSettingsModal.updateDomainsList(filteredDomains);
        });

        // File Upload Modal events
        this.fileUploadModal.events.on('filesUploaded', (files) => {
            // Later this will handle actual file upload to backend
            console.log('Files ready for upload:', files);
        });

        this.fileUploadModal.events.on('warning', (message) => {
            console.warn(message);
        });

        // Feedback Modal events
        this.feedbackModal.events.on('feedbackSubmitted', (message) => {
            console.log(message);
        });
    
        this.feedbackModal.events.on('feedbackError', (error) => {
            console.error(error);
        });
    }

    init() {
        // Add sidebar to DOM
        document.body.appendChild(this.sidebar.element);

        // Setup menu trigger
        const menuTrigger = document.querySelector('.menu-trigger');
        if (menuTrigger) {
            menuTrigger.addEventListener('click', () => {
                this.sidebar.events.emit('menuTrigger');
            });
        }

        // Initialize with test data
        const testDomain = {
            id: '1',
            name: 'Test Domain',
            fileCount: 0
        };

        // Add to domain manager and update UI
        const domainCard = this.domainManager.addDomain(testDomain);
        this.domainSettingsModal.updateDomainsList([testDomain]);
        
        // Add to container if it exists
        const domainContainer = document.getElementById('domainsContainer');
        if (domainContainer) {
            domainContainer.appendChild(domainCard.element);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
    window.app.init();
});