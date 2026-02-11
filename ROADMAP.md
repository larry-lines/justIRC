# JustIRC Development Roadmap

This document outlines planned improvements and future development for JustIRC. Items are organized by priority and development phase.

**Current Version:** v1.0.1  
**Last Updated:** 11 February 2026

---

## 🎯 High Priority (Next Release v1.1.0)

### Testing & Quality Assurance
- [x] **Expand Test Coverage** (Target: 80%+)
  - ✅ Add integration tests for client-server communication
  - ✅ Add E2E tests for complete workflows (join, message, leave)
  - ✅ Add tests for image transfer functionality
  - ✅ Add tests for operator commands and permissions
  - ✅ Add channel crypto tests for group encryption
  
- [x] **Code Quality Tools**
  - ✅ Integrate `black` for Python code formatting
  - ✅ Integrate `pylint` or `flake8` for linting
  - ✅ Add `mypy` for type checking
  - ✅ Add pre-commit hooks for quality gates

### Security Enhancements
- [x] **Rate Limiting**
  - ✅ Implement per-client rate limits (messages/second)
  - ✅ Implement connection rate limiting (prevent DoS)
  - ✅ Add configurable throttling for image transfers
  
- [x] **Key Rotation**
  - ✅ Add automatic session key rotation after N messages
  - ✅ Implement rekeying protocol for long-running sessions
  - ✅ Add manual rekey command for users
  
- [x] **Enhanced Authentication**
  - ✅ Add optional server-side password authentication
  - ✅ Implement persistent user accounts (optional mode)
  - ✅ Add account lockout after failed attempts
  - ✅ Password change functionality
  
- [x] **Server Hardening**
  - ✅ Add input sanitization and validation
  - ✅ Implement connection timeouts and resource limits
  - ✅ Add blacklist/whitelist for IP addresses
  - ✅ Enhance operator authentication security

### Documentation
- [x] **API Documentation**
  - ✅ Generate API docs using Sphinx or pdoc
  - ✅ Document protocol message formats
  - ✅ Add developer API reference guide
  
- [x] **Contribution Guidelines**
  - ✅ Create CONTRIBUTING.md
  - ✅ Add code of conduct (CODE_OF_CONDUCT.md)
  - ✅ Define issue and PR templates
  - ✅ Add development setup guide

---

## 🚀 Medium Priority (v1.2.0)

### Features

#### Core Chat Features
- [x] **Message History & Persistence**
  - ✅ Optional client-side encrypted message storage
  - ✅ SQLite database for local message history
  - ✅ Search through message history
  - ✅ Export chat logs (encrypted format)

- [ ] **Enhanced Channel Features**
  - Channel topics with permission controls
  - Persistent channel bans and mutes
  - Timed bans (kick with auto-unban)
  - Channel invite system
  - Channel modes (+m moderated, +s secret, etc.)

- [ ] **User Features**
  - User profiles (bio, status message)
  - Custom user statuses (away, busy, DND)
  - Nickname registration and protection
  - User blocking (client-side)
  - User mentions with @ notifications

#### File Sharing
- [ ] **Enhanced File Transfer**
  - Support for any file type (not just images)
  - Resume interrupted transfers
  - Batch file uploads
  - File size limits and validation
  - Progress bars for large transfers

### Code Quality
- [ ] **Refactoring**
  - Split large files (client_gui.py: 2460 lines)
  - Extract common utilities into shared module
  - Reduce code duplication
  - Improve error handling consistency
  
- [ ] **Architecture Improvements**
  - Implement proper event bus/observer pattern
  - Separate business logic from UI (MVC/MVP)
  - Add dependency injection for testability
  - Consider async/await improvements

### Performance & Scalability
- [ ] **Server Performance**
  - Optimize message routing algorithms
  - Add connection pooling
  - Implement message queuing for offline users
  - Redis integration for distributed state
  
- [ ] **Load Testing**
  - Create load testing suite with Locust/JMeter
  - Benchmark message throughput
  - Test concurrent connection limits
  - Performance monitoring and profiling tools

- [ ] **Monitoring & Observability**
  - Prometheus metrics endpoint
  - Grafana dashboards for server stats
  - Structured logging (JSON format)
  - Health check endpoints

### User Experience

#### GUI Improvements
- [ ] **Enhanced GUI Client**
  - Notification system (desktop notifications)
  - Sound alerts for messages
  - System tray integration
  - Emoji picker and reactions
  - Message formatting (bold, italic, code blocks)
  - Markdown rendering support
  - Link previews
  - Dark/light mode toggle
  
- [ ] **Accessibility**
  - Screen reader support
  - Keyboard shortcuts for all actions
  - High contrast themes
  - Configurable font sizes
  - ARIA labels and semantic HTML (if web client)

---

## 🔧 Stability & Polish (v1.3.0)

### Advanced Cryptography
- [ ] **Post-Quantum Cryptography**
  - Add post-quantum key exchange (CRYSTALS-Kyber)
  - Hybrid classic + PQC mode
  - Future-proof against quantum computers
  
- [ ] **Enhanced Privacy**
  - Onion routing for metadata protection
  - Mixnet integration
  - Timing attack mitigation
  - Traffic pattern obfuscation

### Bot Framework
- [ ] **Bot API**
  - Python SDK for bot development
  - Webhook support for bots
  - Bot permission system
  - Example bots (moderation, games, utilities)

---

## 🎙️ Communications (v1.5.0)

### Voice & Video
- [ ] **Voice Chat** (WebRTC)
  - End-to-end encrypted voice calls
  - Push-to-talk functionality
  - Multiple participants support
  
- [ ] **Video Chat** (WebRTC)
  - End-to-end encrypted video calls
  - Screen sharing capability

---

## 🔮 Future Enhancements (v2.0.0+)

### Advanced Features

#### Decentralization
- [ ] **Federation Support**
  - Server-to-server federation protocol
  - Distributed server network
  - Cross-server channels
  - Inter-server encryption

- [ ] **P2P Mode**
  - Peer-to-peer direct connections
  - DHT-based user discovery
  - No central server requirement
  - Hybrid P2P + server mode

#### Multi-Platform
- [ ] **Web Client**
  - Browser-based client using WebSockets
  - Progressive Web App (PWA) support
  - Same E2E encryption as native clients
  
- [ ] **Mobile Applications**
  - Native iOS client (Swift)
  - Native Android client (Kotlin)
  - React Native cross-platform option
  - Push notifications for mobile

#### Enterprise Features
- [ ] **Enterprise Management**
  - LDAP/Active Directory integration
  - Single Sign-On (SSO) support
  - Centralized administration console
  - Audit logging and compliance
  - Data retention policies

### Deployment & Infrastructure

#### Container Orchestration
- [ ] **Kubernetes Support**
  - Helm charts for deployment
  - Horizontal pod autoscaling
  - StatefulSet for persistent state
  - Service mesh integration (Istio)

#### Cloud Providers
- [ ] **Multi-Cloud Deployment**
  - AWS deployment guide and templates
  - Azure deployment guide and templates
  - DigitalOcean one-click deployment
  - Terraform modules for all providers

#### High Availability
- [ ] **HA & Clustering**
  - Multi-instance server deployment
  - Load balancing configuration
  - Session persistence across instances
  - Automatic failover

### Developer Tools

#### Developer Experience
- [ ] **Plugin System**
  - Plugin API for extensions
  - Hot-reload plugin support
  - Official plugin marketplace/registry
  - Documentation for plugin developers

- [ ] **Alternative Clients**
  - Terminal UI client (textual/rich)
  - Emacs client
  - VS Code extension
  - IRC bridge (connect standard IRC clients)

#### Monitoring & Analytics
- [ ] **Analytics Dashboard**
  - Real-time user statistics
  - Message volume metrics
  - Channel activity heatmaps
  - User engagement analytics (privacy-preserving)

### Internationalization
- [ ] **i18n Support**
  - Internationalization framework
  - Translation files for major languages
    - Spanish
    - French
    - German
    - Japanese
    - Chinese (Simplified & Traditional)
    - Portuguese
    - Russian
  - RTL language support (Arabic, Hebrew)
  - Community translation platform (Crowdin)

### Community & Ecosystem

#### Project Management
- [ ] **Project Governance**
  - Establish governance model
  - Create steering committee
  - Define release schedule
  - Security disclosure policy

- [ ] **Community Building**
  - Create official JustIRC server for community
  - Forum or discussion board
  - Monthly development updates
  - Developer Discord/Matrix channel
  - Bug bounty program

#### Education
- [ ] **Learning Resources**
  - Video tutorials (YouTube)
  - Interactive onboarding tutorial
  - Blog posts on security architecture
  - Conference talks and presentations
  - Academic paper on cryptographic design

---

## 📊 Technical Debt & Maintenance

### Dependencies
- [ ] **Dependency Management**
  - Regular security audits (Dependabot)
  - Pin all dependency versions
  - Test against multiple Python versions (3.9-3.13)
  - Minimize dependency footprint

### Compatibility
- [ ] **Platform Support**
  - Test on more Linux distributions
  - macOS native builds and packages
  - ARM architecture support
  - BSD support

---

## 🐛 Known Issues & Bug Fixes

### Current Issues
- [ ] Improve error messages for end users (more user-friendly)
- [ ] Handle server disconnections more gracefully (auto-reconnect)
- [ ] Better handling of very large images (size warnings)
- [ ] Validate file paths before saving received files
- [ ] Improve channel password change flow
- [ ] Add confirmation dialogs for destructive actions

### Performance Issues
- [ ] GUI can freeze with many rapid messages (virtualize message list)
- [ ] Memory usage grows over time (add message pruning)
- [ ] Large file transfers block other operations (better async handling)

---

## 💡 Community Suggestions

We welcome community input! If you have ideas for features or improvements:

1. Open an issue with the `enhancement` label
2. Discuss on our community server: `justIrc.example.com:6667` (when available)
3. Submit a pull request with your implementation
4. Vote on existing proposals by adding 👍 reactions

---

## 📅 Release Schedule

- **v1.1.0** - Q1 2026 (Testing, Security, Documentation) ✅
- **v1.2.0** - Q2 2026 (Features, Performance, UX, Code Quality)
- **v1.3.0** - Q3 2026 (Advanced Crypto, Bot Framework)
- **v1.5.0** - Q4 2026 (Voice & Video Communication)
- **v2.0.0** - Q1 2027 (Federation, P2P, Multi-Platform, Advanced Features)

**Note:** This roadmap is a living document and priorities may shift based on community needs, security requirements, and resource availability.

---

## 🤝 How to Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) (to be created) for information on:
- Setting up your development environment
- Running tests
- Coding standards and style guide
- Submitting pull requests
- Reporting bugs and security issues

---

## 📄 License

JustIRC is released under the MIT License. See [LICENSE](LICENSE) for details.
