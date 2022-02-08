#trails {
  line-width: 4;
  line-smooth: .3;
  [closed = 1] {
    line-color: #A9A9A9;
    line-dasharray: 30, 10;
  }
  [lit = 1] {
    ::case {
      line-width: 8;
      line-color: #FFFF00;
    }
  }
  [lit = 0] {
    [closed = 0] {
      ::case {
        line-width: 8;
        line-color: #000000;
      }
    }
  }
}

#trails {
  [closed = 0] {
    ::fill {
      line-width: 4;
      [difficulty = 'easy'] {
        line-color: #72ca61;
      }
      [difficulty = 'intermediate'] {
        line-color: #1b7bc4;
      }
      [difficulty = 'advanced'] {
        line-color: #000000;
      }
    }
  }
}

#background {
  polygon-fill: rgba(255, 255, 255, 0.6);
}