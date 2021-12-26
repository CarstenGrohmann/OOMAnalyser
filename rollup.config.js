// Rollup.js configuration for OOMAnalyser
//
// Copyright (c) 2017-2021 Carsten Grohmann
// License: MIT (see LICENSE.txt)
// THIS PROGRAM COMES WITH NO WARRANTY

export default {
    input: '__target__/OOMAnalyser.js',
    output: {
        file: 'OOMAnalyser.js',
        name: 'OOMAnalyser',
        format: 'umd'
    }
};