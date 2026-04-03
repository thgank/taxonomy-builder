const calls = [];

function revalidatePath(path) {
  calls.push(path);
}

function __getCalls() {
  return [...calls];
}

function __reset() {
  calls.length = 0;
}

module.exports = {
  revalidatePath,
  __getCalls,
  __reset,
};
