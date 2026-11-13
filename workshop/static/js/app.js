document.addEventListener("DOMContentLoaded", function () {
  // предпросмотр выбранного фото
  document.querySelectorAll("[data-preview]").forEach(function (input) {
    var box = document.querySelector(input.dataset.preview);
    if (!box) return;
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file || !file.type.startsWith("image/")) {
        box.style.display = "none";
        return;
      }
      var reader = new FileReader();
      reader.onload = function (event) {
        box.innerHTML = '<img src="' + event.target.result + '" alt="Предпросмотр фото">';
        box.style.display = "block";
      };
      reader.readAsDataURL(file);
    });
  });

  // сообщения сами скрываются через 7 секунд
  document.querySelectorAll(".alert-dismissible").forEach(function (alert) {
    setTimeout(function () {
      if (window.bootstrap) bootstrap.Alert.getOrCreateInstance(alert).close();
    }, 7000);
  });

  var board = document.querySelector("[data-kanban]");
  if (!board) return;

  function getCookie(name) {
    var value = "; " + document.cookie;
    var parts = value.split("; " + name + "=");
    return parts.length === 2 ? parts.pop().split(";").shift() : "";
  }

  var dragged = null;
  var origin = null;

  board.querySelectorAll(".kanban-card").forEach(function (card) {
    card.addEventListener("dragstart", function (event) {
      dragged = card;
      origin = card.parentElement;
      card.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", card.dataset.id);
    });
    card.addEventListener("dragend", function () {
      card.classList.remove("dragging");
      board.querySelectorAll(".kanban-col").forEach(function (col) {
        col.classList.remove("drag-over");
      });
      dragged = null;
    });
  });

  board.querySelectorAll(".kanban-col").forEach(function (column) {
    var cards = column.querySelector(".kanban-cards");
    column.addEventListener("dragover", function (event) {
      event.preventDefault();
      column.classList.add("drag-over");
    });
    column.addEventListener("dragleave", function () {
      column.classList.remove("drag-over");
    });
    column.addEventListener("drop", function (event) {
      event.preventDefault();
      column.classList.remove("drag-over");
      if (!dragged || dragged.parentElement === cards) return;

      var target = column.dataset.status;
      var url = dragged.dataset.url;
      var previousParent = dragged.parentElement;
      cards.appendChild(dragged);
      updateCounts();

      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({ status: target }),
      })
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(function (data) {
          if (!data.ok) throw new Error(data.error || "Ошибка");
          dragged.dataset.status = data.status;
        })
        .catch(function () {
          previousParent.appendChild(dragged);
          updateCounts();
          window.alert("Не удалось изменить статус. Обновите страницу и попробуйте снова.");
        });
    });
  });

  function updateCounts() {
    board.querySelectorAll(".kanban-col").forEach(function (column) {
      var count = column.querySelectorAll(".kanban-card").length;
      var badge = column.querySelector(".kanban-count");
      if (badge) badge.textContent = count;
      var empty = column.querySelector(".kanban-empty");
      if (empty) empty.style.display = count ? "none" : "block";
    });
  }
});
