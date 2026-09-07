// Rollup.js configuration for OOMAnalyser
//
// Copyright (c) 2021-2026 Carsten Grohmann and contributors
// License: MIT (see LICENSE.txt)
// THIS PROGRAM COMES WITH NO WARRANTY

export default {
    input: '__target__/OOMAnalyser.js',
    output: {
        file: 'OOMAnalyser.js',
        name: 'OOMAnalyser',
        banner: '// JavaScript for OOMAnalyser\n' +
            '//\n' +
            '// Copyright (c) 2017-2026 Carsten Grohmann and contributors\n' +
            '// License: MIT (see LICENSE.txt)\n' +
            '// THIS PROGRAM COMES WITH NO WARRANTY',
        format: 'umd'
    }
};
