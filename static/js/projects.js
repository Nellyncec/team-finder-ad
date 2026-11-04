(function () {
  document.addEventListener('DOMContentLoaded', function () {
    const completeButton = document.getElementById('complete-project-btn');
    if (completeButton) {
      completeButton.addEventListener('click', async function (event) {
        event.preventDefault();
        if (!window.confirm('Завершить проект?')) return;

        try {
          const response = await fetch(`/projects/${completeButton.dataset.id}/complete/`, {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCSRFToken(),
              'Content-Type': 'application/json',
            },
          });
          const data = await parseJSON(response);
          if (!response.ok) throw new Error(data.message || 'Не удалось завершить проект.');
          window.location.reload();
        } catch (error) {
          console.error(error);
          window.alert(error.message || 'Ошибка соединения с сервером.');
        }
      });
    }

    const participateButton = document.getElementById('participate-btn');
    if (participateButton) {
      participateButton.addEventListener('click', async function (event) {
        event.preventDefault();

        try {
          const response = await fetch(`/projects/${participateButton.dataset.project}/toggle-participate/`, {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCSRFToken(),
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({}),
          });
          const data = await parseJSON(response);
          if (!response.ok) throw new Error(data.message || 'Не удалось изменить участие.');
          window.location.reload();
        } catch (error) {
          console.error(error);
          window.alert(error.message || 'Ошибка соединения с сервером.');
        }
      });
    }
  });

  async function parseJSON(response) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }

  function getCSRFToken() {
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (const cookie of cookies) {
      const normalized = cookie.trim();
      if (normalized.startsWith('csrftoken=')) {
        return decodeURIComponent(normalized.substring('csrftoken='.length));
      }
    }
    return '';
  }
})();
