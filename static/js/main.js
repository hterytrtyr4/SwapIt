/* SwapIt — front-end behaviors (works without JS; this only enhances). */

document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  /* Auto-dismiss flash alerts after 5 seconds */
  document.querySelectorAll('.flash').forEach(function (alertEl) {
    window.setTimeout(function () {
      if (alertEl.classList.contains('show')) {
        try {
          bootstrap.Alert.getOrCreateInstance(alertEl).close();
        } catch (err) {
          alertEl.style.display = 'none';
        }
      }
    }, 5000);
  });

  /* Confirm destructive actions */
  document.querySelectorAll('.js-confirm-delete').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      var message = form.getAttribute('data-confirm') || 'Are you sure?';
      if (!window.confirm(message)) {
        event.preventDefault();
      }
    });
  });

  /* Live image preview on the add/edit item forms */
  var imageInput = document.getElementById('image');
  var imagePreviewWrap = document.querySelector('.si-upload-preview');
  var imagePreview = document.getElementById('imagePreview');

  if (imageInput && imagePreviewWrap && imagePreview) {
    imageInput.addEventListener('change', function () {
      var file = imageInput.files && imageInput.files[0];
      if (!file) {
        imagePreviewWrap.classList.add('d-none');
        return;
      }
      var reader = new FileReader();
      reader.onload = function (event) {
        imagePreview.src = event.target.result;
        imagePreviewWrap.classList.remove('d-none');
      };
      reader.readAsDataURL(file);
    });
  }
});
