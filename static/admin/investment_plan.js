document.addEventListener("DOMContentLoaded", function () {
    function updateSelectedDaysField() {
        const planType = document.getElementById('id_plan_type').value;
        const selectedDaysContainer = document.querySelector('#id_selected_days').parentElement;
        const selectedDays = document.getElementById('id_selected_days');

        if (!selectedDays) return;

        // Clear previous options
        selectedDays.innerHTML = '';

        if (planType === 'daily' || planType === 'weekly') {
            const days = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
            const labels = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];

            days.forEach((day, index) => {
                const option = document.createElement('option');
                option.value = day;
                option.textContent = labels[index];
                selectedDays.appendChild(option);
            });

            // Multi or single select
            selectedDays.multiple = planType === 'daily';
            selectedDays.size = planType === 'daily' ? 7 : 1;

        } else if (planType === 'monthly') {
            for (let i = 1; i <= 31; i++) {
                const option = document.createElement('option');
                option.value = i;
                option.textContent = `Date ${i}`;
                selectedDays.appendChild(option);
            }
            selectedDays.multiple = false;
            selectedDays.size = 1;
        }
    }

    const planTypeField = document.getElementById('id_plan_type');
    if (planTypeField) {
        planTypeField.addEventListener('change', updateSelectedDaysField);
        updateSelectedDaysField();  // initial load
    }
});
