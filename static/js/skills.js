(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', () => {
        const showFormButton = document.getElementById('show-skill-form-btn');
        const inputWrapper = document.getElementById('skill-input-wrapper');
        const input = document.getElementById('skill-input');
        const addButton = document.getElementById('add-skill-btn');
        const container = document.getElementById('skills-list-container');
        const suggestions = document.getElementById('skill-suggestions');
        const message = document.getElementById('skill-message');

        if (!showFormButton || !inputWrapper || !input || !addButton || !container) {
            return;
        }

        const userId = input.dataset.userId;
        let searchTimer = null;
        let searchController = null;

        function showMessage(text, isError = false) {
            if (!message) return;
            message.textContent = text;
            message.classList.toggle('skill-message-error', isError);
        }

        function hideSuggestions() {
            suggestions.classList.add('hidden');
            suggestions.replaceChildren();
        }

        function setFormVisible(visible) {
            inputWrapper.classList.toggle('hidden', !visible);
            showFormButton.classList.toggle('hidden', visible);
            if (visible) {
                input.focus();
            } else {
                hideSuggestions();
            }
        }

        function createSuggestion(label, onSelect, className = '') {
            const item = document.createElement('li');
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = label;
            if (className) item.className = className;
            button.addEventListener('click', onSelect);
            item.appendChild(button);
            suggestions.appendChild(item);
        }

        function renderSuggestions(skills, query) {
            suggestions.replaceChildren();

            skills.forEach((skill) => {
                createSuggestion(skill.name, () => {
                    addSkill({ skill_id: skill.id }, skill.name);
                });
            });

            const hasExactMatch = skills.some(
                (skill) => skill.name.toLocaleLowerCase() === query.toLocaleLowerCase()
            );
            if (!hasExactMatch) {
                createSuggestion(
                    `Создать «${query}»`,
                    () => addSkill({ name: query }, query),
                    'create-new'
                );
            }
            suggestions.classList.remove('hidden');
        }

        async function loadSuggestions(query) {
            if (searchController) searchController.abort();
            searchController = new AbortController();

            try {
                const response = await fetch(`/users/skills/?q=${encodeURIComponent(query)}`, {
                    signal: searchController.signal,
                });
                if (!response.ok) throw new Error('Не удалось получить подсказки.');
                const skills = await response.json();
                if (input.value.trim() === query) {
                    renderSuggestions(skills, query);
                }
            } catch (error) {
                if (error.name !== 'AbortError') {
                    console.error(error);
                    showMessage('Ошибка при загрузке подсказок.', true);
                }
            }
        }

        function appendSkillChip(skillId, name) {
            const emptyMessage = container.querySelector('.no-skills');
            if (emptyMessage) emptyMessage.remove();

            const chip = document.createElement('div');
            chip.className = 'skill-tag';
            chip.dataset.skillId = skillId;

            const label = document.createElement('span');
            label.textContent = name;

            const removeButton = document.createElement('button');
            removeButton.type = 'button';
            removeButton.className = 'remove-skill-btn';
            removeButton.dataset.skillId = skillId;
            removeButton.setAttribute('aria-label', `Удалить навык ${name}`);
            removeButton.textContent = '×';

            chip.append(label, removeButton);
            container.appendChild(chip);
        }

        async function addSkill(payload, displayName) {
            showMessage('');
            try {
                const response = await fetch(`/users/${userId}/skills/add/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                        'X-CSRFToken': getCSRFToken(),
                    },
                    body: new URLSearchParams(payload),
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Не удалось добавить навык.');

                if (data.added) {
                    appendSkillChip(data.skill_id, displayName);
                    showMessage('Навык добавлен.');
                } else {
                    showMessage('Этот навык уже добавлен.');
                }
                input.value = '';
                hideSuggestions();
                input.focus();
            } catch (error) {
                console.error(error);
                showMessage(error.message || 'Ошибка соединения с сервером.', true);
            }
        }

        showFormButton.addEventListener('click', () => setFormVisible(true));

        input.addEventListener('input', () => {
            window.clearTimeout(searchTimer);
            const query = input.value.trim();
            if (!query) {
                hideSuggestions();
                return;
            }
            searchTimer = window.setTimeout(() => loadSuggestions(query), 250);
        });

        input.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                addButton.click();
            }
            if (event.key === 'Escape') hideSuggestions();
        });

        addButton.addEventListener('click', () => {
            const query = input.value.trim();
            if (!query) {
                showMessage('Введите название навыка.', true);
                return;
            }
            addSkill({ name: query }, query);
        });

        container.addEventListener('click', async (event) => {
            const removeButton = event.target.closest('.remove-skill-btn');
            if (!removeButton) return;

            const skillId = removeButton.dataset.skillId;
            const chip = removeButton.closest('.skill-tag');
            try {
                const response = await fetch(`/users/${userId}/skills/${skillId}/remove/`, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCSRFToken() },
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Не удалось удалить навык.');

                chip.remove();
                if (!container.querySelector('.skill-tag')) {
                    const emptyMessage = document.createElement('p');
                    emptyMessage.className = 'no-skills';
                    emptyMessage.textContent = 'Пока нет добавленных навыков';
                    container.appendChild(emptyMessage);
                }
                showMessage('Навык удалён.');
            } catch (error) {
                console.error(error);
                showMessage(error.message || 'Ошибка соединения с сервером.', true);
            }
        });

        function getCSRFToken() {
            const inputToken = inputWrapper.querySelector('input[name="csrfmiddlewaretoken"]');
            if (inputToken) return inputToken.value;

            const cookies = document.cookie ? document.cookie.split(';') : [];
            for (const cookie of cookies) {
                const normalized = cookie.trim();
                if (normalized.startsWith('csrftoken=')) {
                    return decodeURIComponent(normalized.substring('csrftoken='.length));
                }
            }
            return '';
        }
    });
})();
