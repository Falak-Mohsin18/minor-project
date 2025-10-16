document.addEventListener('DOMContentLoaded', function() {
    // Confirmation before deleting a transaction
    const deleteLinks = document.querySelectorAll('.delete-link');
    deleteLinks.forEach(link => {
        link.addEventListener('click', function(event) {
            if (!confirm("Are you sure you want to delete this transaction?")) {
                event.preventDefault();
            }
        });
    });

    // Basic form validation
    const form = document.querySelector('form');
    form.addEventListener('submit', function(event) {
        const amountInput = document.querySelector('#amount');
        const gstInput = document.querySelector('#gst_percentage');

        if (amountInput.value <= 0) {
            alert("Amount must be greater than zero.");
            event.preventDefault();
        }

        if (gstInput.value < 0 || gstInput.value > 100) {
            alert("GST percentage must be between 0 and 100.");
            event.preventDefault();
        }
    });
});