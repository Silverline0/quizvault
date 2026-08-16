const fs = require('fs');

const data = JSON.parse(fs.readFileSync('/C/Users/s3udi/projects/Quizzes/public/data/uveitis-bcsc.json', 'utf8'));

// Find question with ID 39
const q39 = data.find(q => q.id === 39);

if (q39) {
  console.log('Question ID 39:');
  console.log('  question:', q39.question);
  console.log('  correctAnswer:', q39.correctAnswer);
  console.log('  options:', JSON.stringify(q39.options, null, 2));
  console.log('  Full object:', JSON.stringify(q39, null, 2));
}
