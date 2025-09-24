(function ($) {
  function resetSlots($slotSelect, $status, message) {
    $slotSelect.empty();
    $slotSelect.append('<option value="" disabled selected>' + message + '</option>');
    $slotSelect.prop('disabled', true);
    $status.text(message);
  }

  function populateSlots($slotSelect, $status, slots, selectedValue) {
    $slotSelect.empty();
    if (!slots.length) {
      resetSlots($slotSelect, $status, msg);
      return;
    }

    $slotSelect.append('<option value="" disabled>Select a time</option>');
    slots.forEach(function (slot) {
      var option = $('<option></option>')
        .attr('value', slot.value)
        .text(slot.label + ' (' + slot.tutor_count + ' tutor' + (slot.tutor_count === 1 ? '' : 's') + ' available)');
      if (selectedValue && selectedValue === slot.value) {
        option.attr('selected', 'selected');
      }
      $slotSelect.append(option);
    });
    $slotSelect.prop('disabled', false);
    if (!selectedValue) {
      $slotSelect.prop('selectedIndex', 1);
    }
    $status.text('Select a time to confirm your session.');
  }

  $(function () {
    var $form = $('#booking-form');
    if (!$form.length) {
      return;
    }

    var availabilityUrl = $form.data('availabilityUrl') || '/availability';
    var $subject = $('#subject_id');
    var $date = $('#date');
    var $slotSelect = $('#start_time');
    var $status = $('#slot-status');
    var initialSelected = $slotSelect.data('selected') || '';

    function maybeFetchSlots(trigger) {
      var subjectId = ($subject.val() || '').trim();
      var dateVal = ($date.val() || '').trim();

      if (!subjectId || !dateVal) {
        resetSlots($slotSelect, $status, 'Choose a subject and date to load available times.');
        return;
      }

      console.debug('[booking] fetching slots', { subjectId: subjectId, date: dateVal, trigger: trigger });
      $status.text('Loading available times...');
      $slotSelect.prop('disabled', true);

      $.getJSON(availabilityUrl, {
        subject_id: subjectId,
        date: dateVal,
        _: Date.now(),
      })
        .done(function (data) {
          console.debug('[booking] slots response', data);
          var selectedValue = trigger === 'initial' ? initialSelected : $slotSelect.data('selected') || '';
          var slots = (data && data.slots) || [];
          if (!slots.length) {
            var msg = (data && data.message) || 'No sessions available on that date. Please choose another.';
            resetSlots($slotSelect, $status, msg);
            $slotSelect.data('selected', '');
            return;
          }
          populateSlots($slotSelect, $status, slots, selectedValue);
          if (data && data.message) {
            $status.text(data.message);
          }
          $slotSelect.data('selected', '');
        })
        .fail(function (jqXHR, textStatus) {
          console.error('[booking] availability error', textStatus, jqXHR.status, jqXHR.responseText);
          resetSlots($slotSelect, $status, 'Unable to load times. Please try again.');
        });
    }

    $subject.on('change input', function () {
      maybeFetchSlots('subject');
    });

    $date.on('change input', function () {
      maybeFetchSlots('date');
    });

    if ($subject.val() && $date.val()) {
      maybeFetchSlots('initial');
    } else {
      resetSlots($slotSelect, $status, 'Choose a subject and date to load available times.');
    }
  });
})(jQuery);
