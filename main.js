
const generateBtn = document.getElementById('generate-btn');
const numberContainer = document.querySelector('.number-container');
const historyList = document.getElementById('history-list');

generateBtn.addEventListener('click', () => {
    numberContainer.innerHTML = ''; // Clear previous numbers
    const numbers = generateUniqueNumbers(6, 1, 45);
    displayNumbers(numbers);
    addTohistory(numbers);
});

function generateUniqueNumbers(count, min, max) {
    const numbers = new Set();
    while (numbers.size < count) {
        numbers.add(Math.floor(Math.random() * (max - min + 1)) + min);
    }
    return Array.from(numbers).sort((a, b) => a - b);
}

function displayNumbers(numbers) {
    numbers.forEach(number => {
        const numberBall = document.createElement('div');
        numberBall.classList.add('number-ball');
        numberBall.textContent = number;
        numberBall.style.backgroundColor = getBallColor(number);
        numberContainer.appendChild(numberBall);
    });
}

function addTohistory(numbers) {
    const listItem = document.createElement('li');
    listItem.textContent = numbers.join(', ');
    historyList.prepend(listItem);
}

function getBallColor(number) {
    if (number <= 10) return '#fbc400'; // Yellow
    if (number <= 20) return '#69c8f2'; // Blue
    if (number <= 30) return '#ff7272'; // Red
    if (number <= 40) return '#aaa'; // Gray
    return '#b0d840'; // Green
}
