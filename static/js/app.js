// Classification voting functionality
document.addEventListener('DOMContentLoaded', function() {
    // Handle Submit Classification button
    document.querySelectorAll('.submit-vote-btn').forEach(button => {
        button.addEventListener('click', function() {
            const noteCard = this.closest('.note-card');
            const noteIndex = noteCard.dataset.noteIndex;
            const voteStatus = noteCard.querySelector('.vote-status');

            // Get checked checkboxes
            const checkboxes = noteCard.querySelectorAll('.classification-checkbox:checked');
            const components = Array.from(checkboxes).map(cb => cb.value);

            // Validate: at least one of O or W
            if (!components.includes('o') && !components.includes('w')) {
                showNotification('Please select at least O or W', 'error');
                return;
            }

            // Sort alphabetically: ['w', 'a', 'o'] → ['a', 'o', 'w']
            components.sort();

            // Check if user wants to vote on all identical notes
            const voteAllCheckbox = noteCard.querySelector('.vote-all-identical');
            const voteAll = voteAllCheckbox && voteAllCheckbox.checked;

            // Show loading spinner
            voteStatus.style.display = 'block';
            this.disabled = true;

            const endpoint = voteAll ? '/vote-identical' : '/vote';
            const requestBody = voteAll ?
                {
                    note_text: voteAllCheckbox.dataset.noteText,
                    components: components
                } :
                {
                    bib_id: BIB_ID,
                    note_index: parseInt(noteIndex),
                    components: components
                };

            fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (voteAll) {
                        // Bulk vote success - reload page to show updated states
                        showNotification(
                            `Vote applied to ${data.total_notes} identical notes! Reloading...`,
                            'success'
                        );
                        setTimeout(() => location.reload(), 1500);
                    } else {
                        // Single vote success
                        try {
                            // Update vote distribution display
                            updateVoteDisplay(noteCard, data.distribution, components.join(''));

                            // Update who voted section
                            if (data.voters) {
                                updateVotersDisplay(noteCard, data.voters);
                            }

                            showNotification(
                                `Vote recorded! Consensus: ${data.consensus.toUpperCase()} at ${Math.round(data.consensus_probability * 100)}%`,
                                'success'
                            );

                            // Remove "needs review" badge if present
                            const needsReviewBadge = noteCard.querySelector('.badge.bg-warning');
                            if (needsReviewBadge && needsReviewBadge.textContent.includes('Needs Review')) {
                                needsReviewBadge.remove();
                            }

                            // Remove incomplete vote warning
                            const warningAlert = noteCard.querySelector('.alert-warning');
                            if (warningAlert) {
                                warningAlert.remove();
                            }

                            // Mark note as voted and hide if toggle is active
                            noteCard.dataset.userVoted = 'true';

                            // Check if hide voted notes toggle is active (from record.html)
                            const hideToggle = document.getElementById('hideVotedNotesToggle');
                            if (hideToggle && hideToggle.checked) {
                                // Hide the note card with a fade effect
                                noteCard.style.transition = 'opacity 0.3s';
                                noteCard.style.opacity = '0';
                                setTimeout(() => {
                                    noteCard.style.display = 'none';
                                    // Update hidden count
                                    updateHiddenNotesCount();
                                }, 300);
                            }
                        } catch (error) {
                            console.error('Error updating displays:', error);
                            showNotification('Vote saved, but error updating display: ' + error.message, 'warning');
                        }
                    }
                } else {
                    showNotification('Error: ' + data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Network error occurred', 'error');
            })
            .finally(() => {
                voteStatus.style.display = 'none';
                this.disabled = false;
            });
        });
    });

    // Enable/disable Submit button based on O/W checkbox state
    document.querySelectorAll('.classification-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const noteCard = this.closest('.note-card');
            const submitBtn = noteCard.querySelector('.submit-vote-btn');
            const noteIndex = noteCard.dataset.noteIndex;
            const oChecked = noteCard.querySelector(`#check_o_${noteIndex}`).checked;
            const wChecked = noteCard.querySelector(`#check_w_${noteIndex}`).checked;

            // Enable Submit only if at least one of O or W is checked
            submitBtn.disabled = !(oChecked || wChecked);
        });
    });

    // Initialize Submit button states on page load
    document.querySelectorAll('.note-card').forEach(noteCard => {
        const noteIndex = noteCard.dataset.noteIndex;
        const submitBtn = noteCard.querySelector('.submit-vote-btn');
        const oChecked = noteCard.querySelector(`#check_o_${noteIndex}`).checked;
        const wChecked = noteCard.querySelector(`#check_w_${noteIndex}`).checked;

        // Enable Submit only if at least one of O or W is checked
        submitBtn.disabled = !(oChecked || wChecked);
    });

    // Toggle votes visibility
    document.querySelectorAll('.toggle-votes-btn').forEach(button => {
        button.addEventListener('click', function() {
            const noteCard = this.closest('.note-card');
            const voteDistribution = noteCard.querySelector('.vote-distribution');
            const votersSection = noteCard.querySelector('.voters-section');

            // Toggle visibility
            if (voteDistribution.style.display === 'none') {
                voteDistribution.style.display = 'block';
                votersSection.style.display = 'block';
                this.innerHTML = '<i class="fas fa-eye-slash"></i> Hide Other Votes';
            } else {
                voteDistribution.style.display = 'none';
                votersSection.style.display = 'none';
                this.innerHTML = '<i class="fas fa-eye"></i> Show Other Votes';
            }
        });
    });

    // Keyboard navigation
    document.addEventListener('keydown', function(e) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return; // Don't interfere with form inputs
        }

        if (e.key === 'ArrowLeft') {
            const prevButton = document.querySelector('a[href*="record/"][href*="Previous"]');
            if (prevButton && !prevButton.disabled) {
                window.location.href = prevButton.href;
            }
        } else if (e.key === 'ArrowRight') {
            const nextButton = document.querySelector('a[href*="record/"][href*="Next"]');
            if (nextButton && !nextButton.disabled) {
                window.location.href = nextButton.href;
            }
        }
    });
});

// Notification system
function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.notification-toast');
    existingNotifications.forEach(notification => notification.remove());
    
    // Create new notification
    const notification = document.createElement('div');
    notification.className = `notification-toast alert alert-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} alert-dismissible fade show`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1050;
        min-width: 300px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    `;
    
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 3000);
}

// Helper function to update vote distribution display
function updateVoteDisplay(noteCard, distribution, userVote) {
    const voteDistDiv = noteCard.querySelector('.vote-distribution');

    if (distribution.total === 0) {
        voteDistDiv.innerHTML = '<small class="text-warning"><strong>No votes yet</strong> - be the first to classify!</small>';
        return;
    }

    // Build vote badges HTML
    let html = '<small class="text-muted"><strong>All Votes:</strong><br>';

    // Sort by count descending
    const sortedVotes = Object.entries(distribution.votes).sort((a, b) => b[1] - a[1]);

    for (const [classification, count] of sortedVotes) {
        const prob = distribution.probabilities[classification];
        const isConsensus = classification === distribution.consensus;
        const badgeClass = isConsensus ? 'success' : 'secondary';
        html += `<span class="badge bg-${badgeClass} me-1">${classification.toUpperCase()}: ${Math.round(prob * 100)}% (${count})</span>`;
    }

    html += '</small><br><small><strong>Consensus:</strong> ';
    html += `<span class="badge bg-primary">${distribution.consensus.toUpperCase()}</span> `;
    html += `at ${Math.round(distribution.consensus_probability * 100)}% confidence `;
    html += `(${distribution.total} vote${distribution.total !== 1 ? 's' : ''})`;

    if (distribution.is_contentious) {
        html += ' <span class="badge bg-warning text-dark">CONTENTIOUS</span>';
    }

    html += '</small>';

    // Add component breakdown
    if (distribution.component_breakdown) {
        html += '<br><small class="text-muted mt-2"><strong>Component Breakdown:</strong><br>';
        html += `Has O: ${distribution.component_breakdown.o_percentage}% (${distribution.component_breakdown.o_count} votes)<br>`;
        html += `Has W: ${distribution.component_breakdown.w_percentage}% (${distribution.component_breakdown.w_count} votes)<br>`;
        html += `Has A: ${distribution.component_breakdown.a_percentage}% (${distribution.component_breakdown.a_count} votes)`;
        html += '</small>';
    }

    if (userVote) {
        html += `<br><small class="text-info"><strong>Your vote:</strong> ${userVote.toUpperCase()}</small>`;
    }

    voteDistDiv.innerHTML = html;
}

// Helper function to update voters display
function updateVotersDisplay(noteCard, voters) {
    const votersSection = noteCard.querySelector('.voters-section');

    // Check if element exists
    if (!votersSection) {
        console.error('Voters section not found in note card');
        return;
    }

    if (!voters || Object.keys(voters).length === 0) {
        votersSection.innerHTML = `
            <h6 class="mb-2">Who Voted?</h6>
            <small class="text-muted">No votes yet</small>
        `;
        return;
    }

    try {
        // Build voters list HTML
        let html = '<h6 class="mb-2">Who Voted?</h6><div class="voters-list">';

        // Sort classifications for consistent display
        const sortedClassifications = Object.keys(voters).sort();

        for (const classification of sortedClassifications) {
            const users = voters[classification];
            html += '<div class="mb-2">';
            html += '<span class="badge bg-primary">' + classification.toUpperCase() + '</span>';
            html += '<div class="mt-1">';

            for (const username of users) {
                html += '<small class="badge bg-secondary me-1">' + username + '</small>';
            }

            html += '</div></div>';
        }

        html += '</div>';
        votersSection.innerHTML = html;
    } catch (error) {
        console.error('Error updating voters display:', error);
    }
}

// Helper function to get Bootstrap color class for classification
function getColorForClassification(classification) {
    const colors = {
        'w': 'info',
        'o': 'warning',
        'a': 'success',
        'ow': 'secondary',
        'aw': 'dark',
        'ao': 'primary',
        'aow': 'purple'
    };
    return colors[classification] || 'secondary';
}

// ===== SIMILAR NOTES FUNCTIONALITY =====

// Global variable to store current note card reference
let currentNoteCardForSimilar = null;

// Find Similar Notes button handler
document.querySelectorAll('.find-similar-btn').forEach(button => {
    button.addEventListener('click', function() {
        const noteText = this.dataset.noteText;
        const noteCard = this.closest('.note-card');

        // Store reference for later use
        currentNoteCardForSimilar = noteCard;

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('similarNotesModal'));
        modal.show();

        // Populate original note text
        document.getElementById('originalNoteText').textContent = noteText;

        // Show loading, hide results/empty
        document.getElementById('similarNotesLoading').style.display = 'block';
        document.getElementById('similarNotesList').innerHTML = '';
        document.getElementById('similarNotesEmpty').style.display = 'none';
        document.getElementById('selectedCount').textContent = '0';

        // Disable apply button until notes are loaded
        document.getElementById('applyToSimilarBtn').disabled = true;

        // Find similar notes
        fetch('/find-similar-notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                note_text: noteText,
                threshold: 85
            })
        })
        .then(response => response.json())
        .then(data => {
            // Hide loading
            document.getElementById('similarNotesLoading').style.display = 'none';

            if (data.success) {
                if (data.similar_notes.length === 0) {
                    // No results
                    document.getElementById('similarNotesEmpty').style.display = 'block';
                } else {
                    // Show results
                    populateSimilarNotesList(data.similar_notes, data.search_time_ms);
                    document.getElementById('applyToSimilarBtn').disabled = false;
                }
            } else {
                showNotification('Error finding similar notes: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            document.getElementById('similarNotesLoading').style.display = 'none';
            showNotification('Network error occurred while searching', 'error');
        });
    });
});

// Populate similar notes list in modal
function populateSimilarNotesList(similarNotes, searchTimeMs) {
    const listContainer = document.getElementById('similarNotesList');

    let html = '<div class="alert alert-success py-2 mb-3">';
    html += `<i class="fas fa-check-circle"></i> Found ${similarNotes.length} similar note${similarNotes.length !== 1 ? 's' : ''} `;
    html += `<small class="text-muted">(searched in ${searchTimeMs}ms)</small>`;
    html += '</div>';

    html += '<div class="list-group mb-3">';

    similarNotes.forEach((note, index) => {
        html += `
            <label class="list-group-item list-group-item-action">
                <div class="d-flex align-items-start">
                    <input class="form-check-input me-3 mt-1 flex-shrink-0 similar-note-checkbox"
                           type="checkbox"
                           value="${note.note_id}"
                           data-record="${note.record_bib}"
                           data-note-index="${note.note_index}">
                    <div class="flex-grow-1">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <strong>Record ${note.record_bib}, Note ${note.note_index}</strong>
                            <span class="badge bg-success">${note.similarity}% similar</span>
                        </div>
                        <small class="text-muted">${escapeHtml(note.text)}</small>
                    </div>
                </div>
            </label>
        `;
    });

    html += '</div>';

    // Add select all / deselect all buttons
    html += '<div class="d-flex gap-2 mb-2">';
    html += '<button class="btn btn-sm btn-outline-primary" id="selectAllSimilar">';
    html += '<i class="fas fa-check-square"></i> Select All</button>';
    html += '<button class="btn btn-sm btn-outline-secondary" id="deselectAllSimilar">';
    html += '<i class="fas fa-square"></i> Deselect All</button>';
    html += '</div>';

    listContainer.innerHTML = html;

    // Add event listeners
    document.querySelectorAll('.similar-note-checkbox').forEach(cb => {
        cb.addEventListener('change', updateSelectedCount);
    });

    document.getElementById('selectAllSimilar').addEventListener('click', function() {
        document.querySelectorAll('.similar-note-checkbox').forEach(cb => {
            cb.checked = true;
        });
        updateSelectedCount();
    });

    document.getElementById('deselectAllSimilar').addEventListener('click', function() {
        document.querySelectorAll('.similar-note-checkbox').forEach(cb => {
            cb.checked = false;
        });
        updateSelectedCount();
    });

    // Initialize count
    updateSelectedCount();
}

// Update selected count badge
function updateSelectedCount() {
    const count = document.querySelectorAll('.similar-note-checkbox:checked').length;
    document.getElementById('selectedCount').textContent = count;
}

// Apply classification to similar notes
document.getElementById('applyToSimilarBtn').addEventListener('click', function() {
    if (!currentNoteCardForSimilar) {
        showNotification('Error: Note context lost', 'error');
        return;
    }

    // Get selected note IDs
    const selectedNotes = Array.from(
        document.querySelectorAll('.similar-note-checkbox:checked')
    ).map(cb => parseInt(cb.value));

    if (selectedNotes.length === 0) {
        showNotification('Please select at least one note', 'warning');
        return;
    }

    // Get classification from checkboxes in the note card
    const checkboxes = currentNoteCardForSimilar.querySelectorAll('.classification-checkbox:checked');
    const components = Array.from(checkboxes).map(cb => cb.value);

    // Validate
    if (components.length === 0 || (!components.includes('o') && !components.includes('w'))) {
        showNotification('Please select at least O or W before applying to similar notes', 'error');
        return;
    }

    components.sort();

    // Show loading state
    const applyBtn = this;
    const originalText = applyBtn.innerHTML;
    applyBtn.disabled = true;
    applyBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Applying...';

    // Apply votes
    fetch('/vote-similar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            note_ids: selectedNotes,
            components: components
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(
                `✓ Classification applied to ${data.total_notes} similar note${data.total_notes !== 1 ? 's' : ''}! ` +
                `(${data.votes_created} new, ${data.votes_updated} updated)`,
                'success'
            );

            // Close modal
            bootstrap.Modal.getInstance(document.getElementById('similarNotesModal')).hide();

            // Reload page after brief delay to show updated counts
            setTimeout(() => location.reload(), 1500);
        } else {
            showNotification('Error: ' + (data.error || 'Unknown error'), 'error');
            applyBtn.disabled = false;
            applyBtn.innerHTML = originalText;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Network error occurred while applying votes', 'error');
        applyBtn.disabled = false;
        applyBtn.innerHTML = originalText;
    });
});

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Helper function to update hidden notes count
function updateHiddenNotesCount() {
    const hiddenCountElem = document.getElementById('hiddenNotesCount');
    const hiddenAlertElem = document.getElementById('hiddenNotesAlert');

    if (!hiddenCountElem || !hiddenAlertElem) {
        return; // Elements not on this page
    }

    const noteCards = document.querySelectorAll('.note-card');
    let hiddenCount = 0;

    noteCards.forEach(card => {
        if (card.style.display === 'none') {
            hiddenCount++;
        }
    });

    if (hiddenCount > 0) {
        hiddenCountElem.textContent = hiddenCount;
        hiddenAlertElem.style.display = 'block';
    } else {
        hiddenAlertElem.style.display = 'none';
    }
}

// Navigate to next record with user's specific vote classification
function navigateToMyVote(classification) {
    // Check if we're on a record detail page (BIB_ID is defined)
    if (typeof BIB_ID === 'undefined') {
        // Not on record page - navigate to first record and let route find it
        window.location.href = '/next-my-vote/0/' + classification;
        return;
    }

    // Navigate to next record with this classification
    window.location.href = '/next-my-vote/' + BIB_ID + '/' + classification;
}
